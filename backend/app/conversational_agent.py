import re
import os
import json
from typing import Dict, Any, List, Optional

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

class MasterConversationalAgent:
    """
    Hierarchical Cognitive Dialog Engine.
    Maintains persistent funnel states, understands pragmatic intent ('next', 'e-sign'),
    and provides contextual awareness across all journey milestones (including post-completion).
    """

    SESSIONS: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_session(cls, session_id: str) -> Dict[str, Any]:
        if session_id not in cls.SESSIONS:
            cls.SESSIONS[session_id] = {
                "session_id": session_id,
                "active_funnel": None,    # "LAMF" or "HOME_LOAN"
                "current_stage": "IDLE",
                "awaiting_slot": None,
                "user_data": {
                    "name": "Aryan Agarwal",
                    "pan": None,
                    "portfolio_val": 640000.0,
                    "max_eligible_limit": 320000.0,
                    "selected_amount": 250000.0,
                    "interest_rate": 10.5,
                    "bank_account": "HDFC Bank (XXXX-3294)",
                    "app_id": "APP-LAMF-8831"
                },
                "history": []
            }
        return cls.SESSIONS[session_id]

    @classmethod
    def process_turn(cls, session_id: str, raw_message: str) -> Dict[str, Any]:
        session = cls.get_session(session_id)
        msg = raw_message.strip()
        msg_lower = msg.lower()

        session["history"].append({"role": "user", "content": msg})

        # Layer 1: Pragmatic progression signals
        is_progression = any(k == msg_lower or msg_lower.startswith(k + " ") or msg_lower.endswith(" " + k) for k in [
            "next", "continue", "proceed", "yes", "yeah", "yep", "ok", "okay", "sure", "go ahead", "done", "forward"
        ])

        current_stage = session["current_stage"]
        funnel = session["active_funnel"]

        # STAGE 5: DISBURSED / POST-COMPLETION
        # User already finished agreement and clicks e-sign again or asks status/balance
        if funnel == "LAMF" and current_stage == "DISBURSED":
            amt = session["user_data"].get("selected_amount", 250000.0)
            app_id = session["user_data"]["app_id"]
            bank = session["user_data"]["bank_account"]

            if any(k in msg_lower for k in ["e-sign", "sign", "disburse", "status", "balance", "draw", "money"]):
                resp = (
                    f"Your loan agreement for **{app_id}** is already digitally signed and active! ✅\n\n"
                    f"• **Credit Line Approved**: **₹{amt:,.0f}**\n"
                    f"• **Destination Bank**: {bank}\n"
                    f"• **Disbursal Status**: Processing payout (funds reflect within 2 hours)\n\n"
                    f"You have full flexibility to draw cash anytime, or calculate your monthly interest liability."
                )
                chips = ["Check Withdrawable Balance", "Calculate Interest on ₹50,000", "Return to Home"]
                session["history"].append({"role": "assistant", "content": resp})
                return cls._format_output(resp, chips, "LAMF_ALREADY_ACTIVE", "Core Banking LMS")

        # STAGE 4: AUTOPAY_READY -> User says 'next', 'e-sign', 'proceed'
        if funnel == "LAMF" and current_stage == "AUTOPAY_READY":
            if is_progression or any(k in msg_lower for k in ["sign", "e-sign", "agree", "disburse", "submit"]):
                session["current_stage"] = "DISBURSED"
                amt = session["user_data"].get("selected_amount", 250000.0)
                app_id = session["user_data"]["app_id"]
                bank = session["user_data"]["bank_account"]

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
                session["history"].append({"role": "assistant", "content": resp})
                return cls._format_output(resp, chips, "LAMF_DISBURSEMENT_COMPLETE", "Controlled Workflow Engine")

        # STAGE 3: OTP_PENDING -> User enters 9032
        if funnel == "LAMF" and current_stage == "OTP_PENDING":
            clean_digits = re.sub(r"[^\d]", "", msg)
            if "9032" in msg or clean_digits == "9032" or is_progression:
                session["current_stage"] = "AUTOPAY_READY"
                amt = session["user_data"].get("selected_amount", 250000.0)
                bank = session["user_data"]["bank_account"]

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
                session["history"].append({"role": "assistant", "content": resp})
                return cls._format_output(resp, chips, "LAMF_AUTOPAY_REVIEW", "Core Banking / NPCI Gateway")

        # STAGE 2: AMOUNT_SELECTION -> User enters any number (e.g. 250000, 290000, 300000)
        amt_parsed = cls._parse_amount(msg)
        if (funnel == "LAMF" and current_stage == "PORTFOLIO_FETCHED") or (funnel == "LAMF" and amt_parsed):
            session["current_stage"] = "OTP_PENDING"
            chosen_amt = amt_parsed if amt_parsed else session["user_data"]["selected_amount"]
            max_limit = session["user_data"]["max_eligible_limit"]

            if chosen_amt > max_limit:
                resp = (
                    f"I see you entered **₹{chosen_amt:,.0f}**, but based on the 50% regulatory LTV of your approved portfolio (₹6,40,000), your maximum credit limit is **₹{max_limit:,.0f}**.\n\n"
                    f"Would you like to proceed with the maximum limit of **₹{max_limit:,.0f}**, or enter another amount?"
                )
                chips = [f"Unlock Max ₹{max_limit:,.0f}", "Unlock ₹2,00,000", "Add More Funds"]
                session["history"].append({"role": "assistant", "content": resp})
                return cls._format_output(resp, chips, "LAMF_AMOUNT_EXCEEDED", "Policy Engine")

            session["user_data"]["selected_amount"] = chosen_amt
            monthly_interest = (chosen_amt * 0.105) / 12

            resp = (
                f"Got it! You're setting up a credit limit of **₹{chosen_amt:,.0f}** against your mutual fund portfolio. 🎯\n\n"
                f"• **Interest Rate**: 10.5% p.a. (Only **₹{monthly_interest:,.0f}/month** if fully drawn!)\n"
                f"• **Pay only for what you use**: If you only use ₹50,000, you only pay interest on ₹50,000.\n"
                f"• **Your investments**: Keep earning 100% NAV returns, dividends, and SIP growth.\n\n"
                f"🔒 **Step 3 of 4: Authorize Lien Marking**\n"
                f"CAMS has dispatched an official 4-digit RTA verification OTP to your registered mobile and email.\n\n"
                f"Please enter the 4-digit OTP to confirm (Hint: enter `9032`)."
            )
            chips = ["Enter 9032", "Resend CAMS OTP", "Why lien marking?"]
            session["history"].append({"role": "assistant", "content": resp})
            return cls._format_output(resp, chips, "LAMF_OTP_SENT", "CAMS RTA Gateway")

        # STAGE 1: PAN_INPUT -> User enters PAN
        pan_match = bool(re.search(r'\b[A-Za-z]{5}\d{4}[A-Za-z]\b', msg)) or "pan12345" in msg_lower
        if pan_match or (funnel == "LAMF" and current_stage in ["IDLE", "PAN_INPUT"]):
            session["active_funnel"] = "LAMF"
            session["current_stage"] = "PORTFOLIO_FETCHED"
            pan_val = "PAN12345" if "pan12345" in msg_lower else msg.upper()
            session["user_data"]["pan"] = pan_val

            resp = (
                f"Consolidated Account Statement (CAS) successfully fetched via CAMS & KFintech for PAN **{pan_val}**! 📈🎉\n\n"
                f"• **Name on record**: **Aryan Agarwal**\n"
                f"• **Total Approved Portfolio**: **₹6,40,000**\n"
                f"• **Max Eligible Credit Line (50% LTV)**: **₹3,20,000**\n\n"
                f"**Eligible Holdings Found**:\n"
                f"1. Quant Small Cap Fund — ₹3,00,000 val (Limit: ₹1,50,000)\n"
                f"2. PGIM India Midcap — ₹2,00,000 val (Limit: ₹1,00,000)\n"
                f"3. ICICI Pru Nifty Next 50 — ₹1,40,000 val (Limit: ₹70,000)\n\n"
                f"**Step 2 of 4**: How much credit would you like to unlock today? (e.g. *250000*, *1.5 lakh*, or tap below)."
            )
            chips = ["Unlock ₹1,60,000", "Unlock Full ₹3,20,000", "What is the interest rate?"]
            session["history"].append({"role": "assistant", "content": resp})
            return cls._format_output(resp, chips, "LAMF_PORTFOLIO_LOADED", "CAMS / KFintech RTA")

        # Intent: User wants LAMF
        if any(k in msg_lower for k in ["lamf", "mutual fund loan", "loan against mutual", "pledge funds"]) or msg_lower == "1":
            session["active_funnel"] = "LAMF"
            session["current_stage"] = "PAN_INPUT"
            resp = (
                "Awesome, let's unlock an instant credit line against your mutual funds! 🚀\n\n"
                "With LAMF, your money stays invested, your SIPs continue, and you only pay simple interest on what you actually withdraw.\n\n"
                "**Step 1 of 4**: To fetch your approved portfolio from CAMS/KFintech (with 0 impact on CIBIL), please enter your **PAN number** (e.g. `PAN12345`)."
            )
            chips = ["Use Sample PAN (PAN12345)", "How does CAMS fetch work?", "Is my CIBIL safe?"]
            session["history"].append({"role": "assistant", "content": resp})
            return cls._format_output(resp, chips, "LAMF_START", "Conversational Journey Engine")

        # Intent: User wants Home Loan
        if any(k in msg_lower for k in ["home loan", "housing loan", "buy a home", "property loan"]) or msg_lower == "2":
            session["active_funnel"] = "HOME_LOAN"
            resp = (
                "Exciting times! Let's get you set up for your **Home Loan**! 🏠✨\n\n"
                "To personalize your document requirements and find your lowest interest rate bracket (from 8.65% p.a.):\n\n"
                "Are you **Salaried** or **Self-Employed**?"
            )
            chips = ["👔 Salaried", "💼 Self-Employed"]
            session["history"].append({"role": "assistant", "content": resp})
            return cls._format_output(resp, chips, "HOME_LOAN_START", "Conversational Journey Engine")

        # Status check
        if any(k in msg_lower for k in ["status", "where is my loan", "track application"]):
            resp = (
                f"Hey Aryan Agarwal! I just checked our live loan system for application **APP-HL-1092**.\n\n"
                f"• Current Stage: **Property Technical Valuation**\n"
                f"• Status: `TECHNICAL_VERIFICATION_IN_PROGRESS`\n"
                f"• Pending Documents: **Property Chain Deeds and Latest 3-Month Electricity Bill**\n"
                f"• Estimated Turnaround: **3 business days**\n\n"
                f"Would you like to upload those documents now, or should I explain what format is accepted?"
            )
            chips = ["Upload Pending Documents", "Check Loan Details", "Speak to Loan Officer"]
            session["history"].append({"role": "assistant", "content": resp})
            return cls._format_output(resp, chips, "APPLICATION_STATUS", "Core Loan Origination System (LOS)")

        # Fallback
        resp = (
            f"I'm right here with you! You mentioned: \"{msg}\". 😊\n\n"
            f"How would you like to proceed today?\n"
            f"1️⃣ **Loan Against Mutual Funds (LAMF)** — borrow without liquidating units.\n"
            f"2️⃣ **Home Loan** — tailored interest rates and step-by-step guidance.\n"
            f"3️⃣ **Check Status** of an existing application."
        )
        chips = ["Apply for LAMF", "Home Loan Application", "Check Application Status", "Calculate EMI"]
        session["history"].append({"role": "assistant", "content": resp})
        return cls._format_output(resp, chips, "GENERAL_CONVERSATION", "Master Conversational Agent")

    @classmethod
    def _parse_amount(cls, text: str) -> Optional[float]:
        clean = text.lower().replace(",", "").replace("₹", "").replace("rs", "").replace("unlock", "").replace("max", "").replace("full", "").strip()
        if "lakh" in clean or "lac" in clean:
            num = re.findall(r"[\d\.]+", clean)
            if num:
                return float(num[0]) * 100000
        if "k" in clean:
            num = re.findall(r"[\d\.]+", clean)
            if num:
                return float(num[0]) * 1000
        num = re.findall(r"^\d+$", clean)
        if num:
            val = float(num[0])
            if val >= 10000:
                return val
        num_any = re.findall(r"\b\d{5,9}\b", clean)
        if num_any:
            return float(num_any[0])
        return None

    @classmethod
    def _format_output(cls, text: str, chips: List[str], intent: str, source: str) -> Dict[str, Any]:
        return {
            "basket": "BASKET_2_GUIDED_WORKFLOW",
            "intent": intent,
            "confidence": 0.99,
            "risk_level": "LOW",
            "source_authority": source,
            "response": text,
            "action_chips": chips
        }
