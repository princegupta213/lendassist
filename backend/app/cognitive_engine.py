import re
import os
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from backend.app.gemini_engine import GeminiEngine

class ConversationState:
    """
    Persistent Dialogue State Representation.
    Maintains:
    1. active_goal (e.g. LAMF_APPLICATION, HOME_LOAN)
    2. workflow_state (IDLE, PORTFOLIO_REVIEW, OTP_VERIFICATION, AUTOPAY_REVIEW, DISBURSED)
    3. pending_action (e.g. AWAITING_CREDIT_LIMIT, AWAITING_OTP, AWAITING_ESIGN)
    4. extracted entities (pan, amounts, otp, bank)
    5. conversation memory & interruption stack
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.active_goal: Optional[str] = None
        self.workflow_state: str = "IDLE"
        self.conversation_state: str = "NORMAL"  # NORMAL, ANSWERING, WORKFLOW, ESCALATING, AGENT_CONNECTED
        self.ticket_id: Optional[str] = None
        self.pending_action: Optional[str] = None
        self.failed_attempts: int = 0
        self.interruption_stack: List[Dict[str, Any]] = []
        self.entities: Dict[str, Any] = {
            "pan": None,
            "portfolio_value": 640000.0,
            "max_limit": 320000.0,
            "selected_amount": None,
            "interest_rate": 10.5,
            "bank_account": "HDFC Bank (XXXX-3294)",
            "app_id": "APP-LAMF-8831",
            "application_id": "APP-LAMF-8831",
            "name": "Aryan Agarwal",
            "product_type": "Loan Against Mutual Funds (LAMF)"
        }
        self.history: List[Dict[str, str]] = []

    def set_context(self, app_id: Optional[str]):
        if not app_id or app_id == "GUEST":
            self.entities["app_id"] = None
            self.entities["application_id"] = None
            self.entities["name"] = "Guest Visitor"
            self.entities["product_type"] = None
            return

        self.entities["app_id"] = app_id
        self.entities["application_id"] = app_id
        if "LAMF" in app_id:
            self.entities["name"] = "Aryan Agarwal"
            self.entities["product_type"] = "Loan Against Mutual Funds (LAMF)"
            self.entities["bank_account"] = "HDFC Bank (XXXX-3294)"
            self.entities["portfolio_value"] = 640000.0
            self.entities["max_limit"] = 320000.0
        elif "HL" in app_id:
            self.entities["name"] = "Rahul Sharma"
            self.entities["product_type"] = "Home Loan"
            self.entities["bank_account"] = "ICICI Bank (XXXX-8821)"
            self.entities["sanctioned_amount"] = 2500000.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "active_goal": self.active_goal,
            "workflow_state": self.workflow_state,
            "conversation_state": self.conversation_state,
            "ticket_id": self.ticket_id,
            "failed_attempts": self.failed_attempts,
            "pending_action": self.pending_action,
            "entities": self.entities,
            "interruption_stack": self.interruption_stack
        }


class SemanticInterpreter:
    """
    Separates 5 Core Cognitive Elements:
    1. Speech Act (CONTINUE, QUESTION, PROVIDE_VALUE, INTERRUPTION, CORRECTION, FRUSTRATION)
    2. Intent / Objective (START_LAMF, AMORTIZATION_QUERY, CHARGES_QUERY, STATUS_QUERY, etc.)
    3. Entities (amounts, PAN, OTP, dates)
    4. Sentiment / Friction
    """

    AFFIRMATIVE_SIGNALS = {
        "next", "continue", "proceed", "yes", "yeah", "yep", "ok", "okay", "sure",
        "go ahead", "let's do it", "do it", "fine", "move ahead", "i'm ready",
        "let's continue", "what's next", "take me forward", "done", "sign it", "sign",
        "agree", "disburse", "forward", "yup", "e-sign", "esign"
    }

    QUESTION_SIGNALS = {
        "what", "why", "how", "when", "where", "can i", "is there", "tell me",
        "interest rate", "charges", "fees", "penalty", "margin call", "nifty", "tax"
    }

    FRUSTRATION_SIGNALS = {
        "stop repeating", "fixed answer", "robotic", "sound like a bot", "script",
        "repeat", "useless", "not helping", "talk normally", "i don't understand"
    }

    @classmethod
    def parse_amount(cls, text: str) -> Optional[float]:
        clean = text.lower().replace(",", "").replace("₹", "").replace("rs", "").strip()
        clean = clean.replace("unlock", "").replace("max", "").replace("full", "").strip()
        
        # Words like '3 lakh', '1.5 lac', '400000'
        if re.search(r'\b(?:lakh|lac|l)\b', clean):
            nums = re.findall(r"\d+(?:\.\d+)?", clean)
            if nums:
                try:
                    return float(nums[0]) * 100000
                except ValueError:
                    pass
        if re.search(r'\b\d+(?:\.\d+)?k\b', clean):
            nums = re.findall(r"\d+(?:\.\d+)?", clean)
            if nums:
                try:
                    return float(nums[0]) * 1000
                except ValueError:
                    pass

        words = clean.split()
        for w in words:
            if w.isdigit():
                # 4-digit numbers are likely OTPs, not loan limits
                if len(w) == 4:
                    continue
                val = float(w)
                if val >= 10000:
                    return val

        if clean.isdigit():
            if len(clean) == 4:
                return None
            val = float(clean)
            if val >= 10000:
                return val

        return None

    @classmethod
    def parse_otp(cls, text: str) -> Optional[str]:
        digits = re.findall(r"\b\d{4}\b", text)
        if digits:
            return digits[0]
        return None

    @classmethod
    def parse_pan(cls, text: str) -> Optional[str]:
        clean = text.strip().upper()
        if "PAN12345" in clean:
            return "PAN12345"
        pans = re.findall(r"\b[A-Z]{5}\d{4}[A-Z]\b", clean)
        if pans:
            return pans[0]
        return None

    @classmethod
    def analyze(cls, text: str, state: ConversationState) -> Dict[str, Any]:
        understanding_res = GeminiEngine.understand_message(text, state.to_dict(), state.history)
        u = understanding_res.get("understanding", {})
        d = understanding_res.get("decision", {})
        return {
            "speech_act": u.get("speech_act", "STATEMENT"),
            "intent": u.get("intent", "GENERAL_CONVERSATION"),
            "entities": u.get("entities", {}),
            "raw_text": text,
            "understanding": u,
            "decision": d,
            "full_understanding": understanding_res
        }


class DialogueManager:
    """
    Central Decision & Action Coordinator.
    Interprets user action against ConversationState and orchestrates between:
    - Business Workflow Execution
    - Policy Question Answering (RAG)
    - Interruption Handling & Seamless Resumption
    - Second LLM Humanized Response Generation with Personality Contract
    """

    SESSIONS: Dict[str, ConversationState] = {}

    @classmethod
    def get_state(cls, session_id: str) -> ConversationState:
        if session_id not in cls.SESSIONS:
            cls.SESSIONS[session_id] = ConversationState(session_id)
        return cls.SESSIONS[session_id]

    @classmethod
    def get_or_create_state(cls, session_id: str) -> ConversationState:
        return cls.get_state(session_id)

    @classmethod
    def handle_message(cls, session_id: str, message: str) -> Dict[str, Any]:
        state = cls.get_state(session_id)
        analysis = SemanticInterpreter.analyze(message, state)

        speech_act = analysis["speech_act"]
        intent = analysis["intent"]
        entities = analysis["entities"]

        state.history.append({"role": "user", "content": message})

        # ROUTE -1: SECURITY & SAFETY GUARDRAIL (Prompt Injection, Data Exfiltration, Speculation, Contradiction)
        guardrail_resp = analysis.get("full_understanding", {}).get("guardrail_response")
        if guardrail_resp:
            state.history.append({"role": "assistant", "content": guardrail_resp["response"]})
            return guardrail_resp

        # ROUTE 0: BANK VERIFICATION FAILURE (Adaptive failure handling)
        if intent == "BANK_VERIFICATION_FAILURE":
            return cls._handle_bank_verification_failure(state, analysis)

        # ROUTE 0A: COMPOUND QUERY & ACTION (Mixed Intent)
        if intent == "MIXED_QUERY_AND_ACTION":
            return cls._handle_compound_query_and_action(state, message)

        # ROUTE 0B: WORKFLOW RETRY / CONTINUATION (Retry penny drop)
        if intent == "WORKFLOW_CONTINUATION":
            return cls._handle_workflow_retry(state)

        # ROUTE 0C: CLARIFICATION REQUIRED (Ambiguity / Contradiction)
        if intent == "CLARIFICATION_REQUIRED":
            resp = (
                "Could you please clarify your request? "
                "Let me know if you would like to apply for a loan, check an existing application, or connect with a specialist."
            )
            chips = ["Check Application Status", "Apply for LAMF", "Connect with an Agent"]
            state.history.append({"role": "assistant", "content": resp})
            return cls._format_response(resp, chips, "CLARIFICATION_REQUIRED", "Dialogue Manager")

        # ROUTE 1: USER FRUSTRATION
        if speech_act in ["FRUSTRATION", "FRUSTRATION_ESCALATION"] or intent in ["EXPRESS_FRUSTRATION", "HUMAN_HANDOFF"]:
            return cls._handle_frustration(state)

        # ROUTE 2: POST-DISBURSEMENT ACTIVE LINE INQUIRIES
        if state.workflow_state == "DISBURSED":
            msg_clean = message.lower().strip()
            if intent == "LAMF_ALREADY_ACTIVE" or speech_act == "CONTINUE" or any(k in msg_clean for k in ["status", "balance", "withdrawable", "limit", "agreement", "payout", "active", "disburs"]):
                return cls._handle_continuation(state)

        # ROUTE 3: TYPE A CONTRACTUAL / HIGH RISK (e.g. Demise / Inheritance)
        if intent == "LOAN_SETTLEMENT_DECEASED":
            return cls._handle_unsupported_contractual(state, analysis)

        # ROUTE 4: TYPE D ACTION REQUEST (Change Bank Account)
        if intent == "CHANGE_BANK_ACCOUNT":
            return cls._handle_change_bank(state, analysis)

        # ROUTE 4B: BANK ACCOUNT DETAILS UPDATE
        if state.active_goal == "BANK_ACCOUNT_CHANGE":
            account_nums = re.findall(r"\b\d{6,18}\b", message)
            if account_nums:
                new_acc = account_nums[-1]
                state.entities["bank_account"] = f"Account ending {new_acc[-4:]}"
                resp = (
                    f"Got it! Updated your bank account to ending **{new_acc[-4:]}**. "
                    "We will verify this with a quick ₹1 penny drop. Ready to proceed?"
                )
                chips = ["Verify with ₹1 Penny Drop", "Cancel Change", "Connect with an Agent"]
                state.history.append({"role": "assistant", "content": resp})
                return cls._format_response(resp, chips, "PROVIDE_VALUE", "Core Banking Gateway")

        # ROUTE 5: QUESTIONS, INTERRUPTIONS & RAG (Agreement explanation, rates, fees, status)
        if speech_act == "QUESTION" or intent in [
            "AGREEMENT_EXPLANATION", "APPLICATION_STATUS", "INQUIRE_FEES",
            "INQUIRE_INTEREST_RATE", "INQUIRE_LIEN_EXPLANATION", "INQUIRE_MARGIN_CALL",
            "INQUIRE_TAX", "POLICY_FAQ"
        ]:
            return cls._handle_question_interruption(state, intent, analysis)

        # ROUTE 6: VALUE PROVISION (PAN, Amount, OTP) - Evaluated contextually
        # If we are waiting for OTP, prioritize OTP input
        if state.workflow_state == "OTP_VERIFICATION" and "otp" in entities:
            return cls._execute_otp_verification(state, entities["otp"])

        if speech_act == "PROVIDE_VALUE":
            return cls._handle_value_provision(state, entities, analysis)

        # ROUTE 7: AFFIRMATIVE PROGRESSION ('next', 'ok', 'proceed', 'yes', 'sign it')
        if speech_act == "CONTINUE":
            return cls._handle_continuation(state)

        # ROUTE 8: WORKFLOW INITIATION
        if intent == "START_LAMF":
            return cls._start_lamf(state)
        elif intent == "START_HOME_LOAN":
            return cls._start_home_loan(state)

        # ROUTE 9: DEFAULT CONVERSATIONAL RESPONSE
        return cls._default_response(state, message)

    @classmethod
    def _handle_frustration(cls, state: ConversationState) -> Dict[str, Any]:
        state.active_goal = None
        state.pending_action = None
        resp = (
            "My sincere apologies for sounding repetitive! 🙏\n\n"
            "Let's drop all scripts and talk like real people. "
            "Tell me where you are in your finances right now — are you looking to borrow against your **mutual funds (LAMF)** without selling them, apply for a **Home Loan**, or check an existing application?"
        )
        chips = ["Start LAMF Step 1", "Home Loan Assistance", "Check Status of My Application"]
        state.history.append({"role": "assistant", "content": resp})
        return cls._format_response(resp, chips, "CONVERSATIONAL_RESET", "Cognitive Dialogue Manager")

    @classmethod
    def _handle_compound_query_and_action(cls, state: ConversationState, message: str) -> Dict[str, Any]:
        bank = state.entities.get("bank_account", "HDFC Bank (XXXX-3294)")
        rate = state.entities.get("interest_rate", 10.5)
        resp = (
            f"Your current interest rate is {rate}% p.a., calculated on the daily reducing balance.\n\n"
            f"Regarding your bank check: the ₹1 penny drop verification encountered an issue with **{bank}**. "
            f"Please verify your IFSC and account details, and I can help you re-initiate the verification."
        )
        chips = ["Try Verification Again", "Change Bank Account", "Connect with an Agent"]
        state.history.append({"role": "assistant", "content": resp})
        return cls._format_response(resp, chips, "MIXED_QUERY_AND_ACTION", "Cognitive Orchestrator")

    @classmethod
    def _handle_unsupported_contractual(cls, state: ConversationState, analysis: Dict[str, Any]) -> Dict[str, Any]:
        answer = GeminiEngine.generate_humanized_response({}, state.to_dict(), analysis.get("full_understanding", {"understanding": {"intent": "LOAN_SETTLEMENT_DECEASED"}}))
        chips = ["Speak with Loan Specialist", "Return to Assistant"]
        state.history.append({"role": "assistant", "content": answer})
        return cls._format_response(answer, chips, "LOAN_SETTLEMENT_DECEASED", "Policy Exception / Legal Desk")

    @classmethod
    def _handle_change_bank(cls, state: ConversationState, analysis: Dict[str, Any]) -> Dict[str, Any]:
        state.active_goal = "BANK_ACCOUNT_CHANGE"
        state.pending_action = "AWAITING_BANK_DETAILS"
        state.interruption_stack.append({"goal": "BANK_ACCOUNT_CHANGE", "action": "AWAITING_BANK_DETAILS"})
        answer = GeminiEngine.generate_humanized_response({}, state.to_dict(), analysis.get("full_understanding", {"understanding": {"intent": "CHANGE_BANK_ACCOUNT"}}))
        chips = ["Provide Bank IFSC", "Keep Current HDFC Bank", "e-Sign Agreement & Disburse"]
        state.history.append({"role": "assistant", "content": answer})
        return cls._format_response(answer, chips, "CHANGE_BANK_ACCOUNT", "Account Verification Gateway")

    @classmethod
    def _handle_question_interruption(cls, state: ConversationState, intent: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Handle linked bank pronoun inquiry
        if analysis.get("entities", {}).get("inquiry") == "linked_bank":
            bank = state.entities.get("bank_account", "HDFC Bank (XXXX-3294)")
            prod = state.entities.get("product_type", "loan")
            app_id = state.entities.get("application_id", "APP-LAMF-8831")
            answer = f"Your {prod} ({app_id}) is linked to **{bank}** for automated repayments and disbursements."
            chips = ["Change Bank Account", "Check Application Status", "Return to Assistant"]
            state.history.append({"role": "assistant", "content": answer})
            return cls._format_response(answer, chips, "APPLICATION_STATUS", "Core Banking Gateway")

        # 2. Handle dynamic application context switch
        app_id_req = analysis.get("entities", {}).get("application_id")
        if app_id_req:
            state.set_context(app_id_req)

        # 3. Interruption preservation
        if state.active_goal == "BANK_ACCOUNT_CHANGE":
            state.interruption_stack.append({"goal": "BANK_ACCOUNT_CHANGE", "action": "AWAITING_BANK_DETAILS"})

        answer = GeminiEngine.generate_humanized_response({}, state.to_dict(), analysis.get("full_understanding", {"understanding": {"intent": intent}}))

        # RESUMPTION PROMPT: If the user was in an active journey, provide continuity
        if state.active_goal == "LAMF_APPLICATION" and state.workflow_state in ["PORTFOLIO_REVIEW", "OTP_VERIFICATION", "AUTOPAY_REVIEW"]:
            resumption = ""
            chips = []
            if state.workflow_state == "PORTFOLIO_REVIEW":
                resumption = "\n\nYour ₹6,40,000 mutual fund portfolio is ready. Would you like to select your loan amount?"
                chips = ["Unlock ₹1,60,000", "Unlock Full ₹3,20,000"]
            elif state.workflow_state == "OTP_VERIFICATION":
                resumption = "\n\nYour CAMS lien verification is currently pending. Enter `9032` whenever you're ready to authorize."
                chips = ["Enter 9032", "Resend OTP"]
            elif state.workflow_state == "AUTOPAY_REVIEW":
                if intent == "AGREEMENT_EXPLANATION":
                    chips = ["e-Sign Agreement & Disburse", "Explain Charges", "Change Bank Account"]
                elif intent == "INQUIRE_FEES":
                    resumption = "\n\nReady to complete e-Sign?"
                    chips = ["e-Sign Agreement & Disburse", "View Key Fact Statement (KFS)", "Change Bank Account"]
                else:
                    resumption = "\n\nReady to complete e-Sign?"
                    chips = ["e-Sign Agreement & Disburse", "View Key Fact Statement (KFS)"]
            
            full_response = answer + resumption
            state.history.append({"role": "assistant", "content": full_response})
            return cls._format_response(full_response, chips, intent, "Knowledge Base + Resumption Engine")

        state.history.append({"role": "assistant", "content": answer})
        return cls._format_response(answer, ["Apply for LAMF", "Home Loan Application", "Check Application Status"], intent, "Knowledge Base (RAG)")

    @classmethod
    def _execute_otp_verification(cls, state: ConversationState, otp_code: str) -> Dict[str, Any]:
        state.workflow_state = "AUTOPAY_REVIEW"
        state.pending_action = "AWAITING_ESIGN"
        amt = state.entities.get("selected_amount", 250000.0)
        bank = state.entities["bank_account"]

        resp = (
            f"✅ **Lien Successfully Authorized with CAMS!**\n\n"
            f"Your mutual fund units remain completely safe in your demat/folio with 100% market upside.\n\n"
            f"📋 **Final Step 4 of 4: AutoPay Setup & Key Fact Statement (KFS)**\n"
            f"• **Destination Bank**: **{bank}**\n"
            f"• **Penny Drop Verification**: Confirmed (₹1 deposited)\n"
            f"• **Sanctioned Limit**: **₹{amt:,.0f}**\n"
            f"• **Interest Rate**: **10.5% p.a.** (Pay ₹0 if not drawn)\n"
            f"• **Foreclosure Penalty**: **₹0 (Nil)**\n\n"
            f"Everything is verified. Ready to e-Sign and get the funds disbursed?"
        )
        chips = ["e-Sign Agreement & Disburse", "View Key Fact Statement (KFS)", "Change Bank Account"]
        state.history.append({"role": "assistant", "content": resp})
        return cls._format_response(resp, chips, "LAMF_AUTOPAY_REVIEW", "Core Banking / NPCI Gateway")

    @classmethod
    def _handle_value_provision(cls, state: ConversationState, entities: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        # 1. PAN Provided
        if "pan" in entities:
            state.active_goal = "LAMF_APPLICATION"
            state.workflow_state = "PORTFOLIO_REVIEW"
            state.pending_action = "AWAITING_CREDIT_LIMIT"
            state.entities["pan"] = entities["pan"]

            resp = (
                f"Consolidated Account Statement (CAS) successfully fetched via CAMS & KFintech for PAN **{entities['pan']}**! 📈🎉\n\n"
                f"• **Name on record**: **Aryan Agarwal**\n"
                f"• **Total Approved Portfolio**: **₹6,40,000**\n"
                f"• **Max Eligible Credit Line (50% LTV)**: **₹3,20,000**\n\n"
                f"**Eligible Holdings Found**:\n"
                f"1. Quant Small Cap Fund — ₹3,00,000 val (Limit: ₹1,50,000)\n"
                f"2. PGIM India Midcap — ₹2,00,000 val (Limit: ₹1,00,000)\n"
                f"3. ICICI Pru Nifty Next 50 — ₹1,40,000 val (Limit: ₹70,000)\n\n"
                f"**Step 2 of 4**: How much credit would you like to unlock today? (e.g. *250000*, *300000*, or tap below)."
            )
            chips = ["Unlock ₹1,60,000", "Unlock Full ₹3,20,000", "What is the interest rate?"]
            state.history.append({"role": "assistant", "content": resp})
            return cls._format_response(resp, chips, "LAMF_PORTFOLIO_LOADED", "CAMS / KFintech RTA")

        # 2. Loan Amount Provided
        if "amount" in entities:
            amt = entities["amount"]
            state.active_goal = "LAMF_APPLICATION"
            max_limit = state.entities["max_limit"]

            if amt > max_limit:
                resp = (
                    f"I see you entered **₹{amt:,.0f}**, but based on the 50% regulatory LTV of your approved portfolio (₹6,40,000), your maximum credit limit is **₹{max_limit:,.0f}**.\n\n"
                    f"Would you like to proceed with the maximum limit of **₹{max_limit:,.0f}**, or enter another amount?"
                )
                chips = [f"Unlock Max ₹{max_limit:,.0f}", "Unlock ₹2,00,000", "Add More Funds"]
                state.history.append({"role": "assistant", "content": resp})
                return cls._format_response(resp, chips, "LAMF_AMOUNT_EXCEEDED", "Policy Engine")

            state.entities["selected_amount"] = amt
            state.workflow_state = "OTP_VERIFICATION"
            state.pending_action = "AWAITING_OTP"
            monthly_interest = (amt * 0.105) / 12

            resp = (
                f"Got it! You're setting up a credit limit of **₹{amt:,.0f}** against your mutual fund portfolio. 🎯\n\n"
                f"• **Interest Rate**: 10.5% p.a. (Only **₹{monthly_interest:,.0f}/month** if fully drawn!)\n"
                f"• **Pay only for what you use**: If you only use ₹50,000, you only pay interest on ₹50,000.\n"
                f"• **Your investments**: Keep earning 100% NAV returns, dividends, and SIP growth.\n\n"
                f"🔒 **Step 3 of 4: Authorize Lien Marking**\n"
                f"CAMS has dispatched an official 4-digit RTA verification OTP to your registered mobile and email.\n\n"
                f"Please enter the 4-digit OTP to confirm (Hint: enter `9032`)."
            )
            chips = ["Enter 9032", "Resend CAMS OTP", "Why lien marking?"]
            state.history.append({"role": "assistant", "content": resp})
            return cls._format_response(resp, chips, "LAMF_OTP_SENT", "CAMS RTA Gateway")

        # 3. OTP Provided
        if "otp" in entities:
            return cls._execute_otp_verification(state, entities["otp"])

        return cls._default_response(state, analysis["raw_text"])

    @classmethod
    def _handle_continuation(cls, state: ConversationState) -> Dict[str, Any]:
        # 1. At AUTOPAY_REVIEW -> Execute Disbursal
        if state.workflow_state == "AUTOPAY_REVIEW" or state.pending_action == "AWAITING_ESIGN":
            state.workflow_state = "DISBURSED"
            state.pending_action = None
            amt = state.entities.get("selected_amount", 250000.0)
            app_id = state.entities["app_id"]
            bank = state.entities["bank_account"]

            resp = (
                f"🎉 **You're All Done! Your LAMF Agreement is Digitally Signed!** 💸\n\n"
                f"• **Application ID**: `{app_id}`\n"
                f"• **Approved Credit Line**: **₹{amt:,.0f}**\n"
                f"• **Disbursal Destination**: {bank}\n"
                f"• **Expected Payout**: Funds will reflect in your account within **2 hours**.\n\n"
                f"Your mutual funds remain 100% invested and earning market growth. You only pay simple interest on what you actually draw.\n\n"
                f"Would you like to check your withdrawable balance or calculate interest for a specific draw amount?"
            )
            chips = ["Check Withdrawable Balance", "Calculate Interest on ₹50,000", "Return to Home"]
            state.history.append({"role": "assistant", "content": resp})
            return cls._format_response(resp, chips, "LAMF_DISBURSEMENT_COMPLETE", "Controlled Workflow Engine")

        # 2. Already Disbursed
        if state.workflow_state == "DISBURSED":
            amt = state.entities.get("selected_amount", 250000.0)
            app_id = state.entities["app_id"]
            bank = state.entities["bank_account"]

            resp = (
                f"Your loan agreement for **{app_id}** is already digitally signed and active! ✅\n\n"
                f"• **Credit Line Approved**: **₹{amt:,.0f}**\n"
                f"• **Destination Bank**: {bank}\n"
                f"• **Disbursal Status**: Processing payout (funds reflect within 2 hours)\n\n"
                f"You have full flexibility to draw cash anytime, or calculate your monthly interest liability."
            )
            chips = ["Check Withdrawable Balance", "Calculate Interest on ₹50,000", "Return to Home"]
            state.history.append({"role": "assistant", "content": resp})
            return cls._format_response(resp, chips, "LAMF_ALREADY_ACTIVE", "Core Banking LMS")

        # 3. At OTP_VERIFICATION -> Remind for OTP
        if state.workflow_state == "OTP_VERIFICATION":
            resp = (
                "We're currently waiting for your CAMS authorization OTP to mark the lien on your mutual funds. 🔒\n\n"
                "Please enter the 4-digit code sent to your mobile (Demo Hint: enter `9032`)."
            )
            chips = ["Enter 9032", "Resend CAMS OTP", "Why is OTP required?"]
            state.history.append({"role": "assistant", "content": resp})
            return cls._format_response(resp, chips, "AWAITING_OTP_REMINDER", "CAMS Gateway")

        # 4. At PORTFOLIO_REVIEW -> Remind for Limit
        if state.workflow_state == "PORTFOLIO_REVIEW":
            resp = (
                f"Your ₹6,40,000 mutual fund portfolio gives you up to **₹3,20,000** in credit line. 📈\n\n"
                f"How much would you like to unlock today? (e.g. *250000*, *300000*, or tap below)."
            )
            chips = ["Unlock ₹1,60,000", "Unlock Full ₹3,20,000", "What is the interest rate?"]
            state.history.append({"role": "assistant", "content": resp})
            return cls._format_response(resp, chips, "AWAITING_LIMIT_REMINDER", "Portfolio Review")

        return cls._default_response(state, "continue")

    @classmethod
    def _start_lamf(cls, state: ConversationState) -> Dict[str, Any]:
        state.active_goal = "LAMF_APPLICATION"
        state.workflow_state = "PAN_INPUT"
        state.pending_action = "AWAITING_PAN"

        resp = (
            "Awesome, let's unlock an instant credit line against your mutual funds! 🚀\n\n"
            "With LAMF, your money stays invested, your SIPs continue, and you only pay simple interest on what you actually withdraw.\n\n"
            "**Step 1 of 4**: To fetch your approved portfolio from CAMS/KFintech (with 0 impact on CIBIL), please enter your **PAN number** (e.g. `PAN12345`)."
        )
        chips = ["Use Sample PAN (PAN12345)", "How does CAMS fetch work?", "Is my CIBIL safe?"]
        state.history.append({"role": "assistant", "content": resp})
        return cls._format_response(resp, chips, "LAMF_START", "Cognitive Dialogue Manager")

    @classmethod
    def _start_home_loan(cls, state: ConversationState) -> Dict[str, Any]:
        state.active_goal = "HOME_LOAN_APPLICATION"
        state.workflow_state = "EMPLOYMENT_INPUT"
        state.pending_action = "AWAITING_EMPLOYMENT"

        resp = (
            "Exciting times! Let's get you set up for your **Home Loan**! 🏠✨\n\n"
            "To personalize your document requirements and find your lowest interest rate bracket (from 8.65% p.a.):\n\n"
            "Are you **Salaried** or **Self-Employed**?"
        )
        chips = ["👔 Salaried", "💼 Self-Employed"]
        state.history.append({"role": "assistant", "content": resp})
        return cls._format_response(resp, chips, "HOME_LOAN_START", "Cognitive Dialogue Manager")

    @classmethod
    def _handle_bank_verification_failure(cls, state: ConversationState, analysis: Dict[str, Any]) -> Dict[str, Any]:
        state.failed_attempts += 1
        bank = state.entities.get("bank_account", "HDFC Bank ending 3294")
        if state.failed_attempts >= 2:
            state.conversation_state = "ESCALATING"
            ticket_num = int(time.time() * 1000) % 100000
            ticket_id = f"TICK-LA-{ticket_num}"
            state.ticket_id = ticket_id
            resp = (
                f"The bank verification has failed again for {bank}. "
                f"Rather than making you retry repeatedly, I have created Priority Ticket **#{ticket_id}** "
                f"and routed your case directly to our **Technical Gateway Operations** team to unblock your account."
            )
            chips = ["View Agent Workspace", "Try Verification Again", "Return to Assistant"]
            state.history.append({"role": "assistant", "content": resp})
            res = cls._format_response(resp, chips, "BANK_VERIFICATION_FAILURE", "Technical Gateway Operations")
            res["basket"] = "BASKET_4_HUMAN_ESCALATION"
            res["escalation_score"] = 0.65
            res["ticket_id"] = ticket_id
            res["ticket"] = {
                "ticket_id": ticket_id,
                "priority": "P2_HIGH",
                "escalation_level": "LEVEL_2_SPECIALIST",
                "customer": {
                    "name": state.entities.get("name", "Aryan Agarwal"),
                    "application_id": state.entities.get("application_id", "APP-LAMF-8831")
                },
                "conversation": {
                    "detected_intent": "BANK_VERIFICATION_FAILURE"
                },
                "ai_recommendation": {
                    "assigned_desk": "Technical Gateway Operations",
                    "reason_for_escalation": f"Repeated bank verification / penny drop failure for {bank}."
                }
            }
            return res

        resp = (
            "The bank verification didn’t go through. "
            "This can happen if the account details or IFSC don’t match the bank records. "
            "Please recheck your account number and IFSC, and I’ll help you retry the verification."
        )
        chips = ["Try Verification Again", "Change Bank Account", "Connect with an Agent"]
        state.history.append({"role": "assistant", "content": resp})
        return cls._format_response(resp, chips, "BANK_VERIFICATION_FAILURE", "NPCI / Bank Verification Gateway")

    @classmethod
    def _handle_workflow_retry(cls, state: ConversationState) -> Dict[str, Any]:
        bank = state.entities.get("bank_account", "HDFC Bank ending 3294")
        resp = (
            f"Re-initiating the ₹1 penny drop verification with NPCI for **{bank}**. "
            "Please ensure your registered mobile number is active to receive the confirmation alert."
        )
        chips = ["Confirm Account Details", "e-Sign Agreement & Disburse", "Connect with an Agent"]
        state.history.append({"role": "assistant", "content": resp})
        return cls._format_response(resp, chips, "WORKFLOW_CONTINUATION", "NPCI / Core Banking Gateway")

    @classmethod
    def _default_response(cls, state: ConversationState, raw_text: str) -> Dict[str, Any]:
        app_id = state.entities.get("application_id") or state.entities.get("app_id")
        app_ctx = f" regarding application {app_id}" if app_id else ""
        resp = (
            f"I want to make sure I assist you accurately with your loan{app_ctx}. "
            "Could you clarify if you'd like to check your application status, continue with Loan Against Mutual Funds, or speak directly with an advisor?"
        )
        chips = ["Check Application Status", "Apply for LAMF", "Connect with an Agent"]
        state.history.append({"role": "assistant", "content": resp})
        return cls._format_response(resp, chips, "CLARIFICATION_REQUIRED", "Master Cognitive Agent")

    @classmethod
    def _format_response(cls, text: str, chips: List[str], intent: str, source: str) -> Dict[str, Any]:
        return {
            "basket": "BASKET_2_GUIDED_WORKFLOW",
            "intent": intent,
            "confidence": 0.99,
            "risk_level": "LOW",
            "source_authority": source,
            "response": text,
            "action_chips": chips
        }
