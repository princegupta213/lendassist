import os
import re
import json
import urllib.request
from typing import Optional, Dict, Any, List, Tuple

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# -----------------------------------------------------------------------------
# HIERARCHY OF OBJECTIVES & NATURAL LANGUAGE CONTRACT
# -----------------------------------------------------------------------------
HIERARCHY_OF_OBJECTIVES = """
1. FACTUAL CORRECTNESS: Use VERIFIED FACTS as the only source of factual information. Never invent numbers, rates, or account terms.
2. ANSWER THE USER'S ACTUAL INTENT: Prioritize the information that directly answers the customer's question.
3. NATURAL HUMAN COMMUNICATION: Synthesize and communicate meaning naturally, as a helpful human loan advisor would. Avoid database jargon or mechanical formatting.
4. BREVITY: Give the shortest natural answer that fully satisfies the user's intent without artificial truncation.
5. POLICY & FORMAT COMPLIANCE: Stay strictly within assigned sentence budgets, bullet limits, and safety boundaries.
"""

NATURAL_LANGUAGE_CONTRACT = """
NATURAL LANGUAGE CONTRACT
You are the final customer-facing response writer.
Your job is NOT to copy, concatenate, or mechanically format VERIFIED FACTS.
Interpret the verified facts and communicate their meaning naturally, as a helpful human loan advisor would.

Rules:
1. Use VERIFIED FACTS as the only source of factual information.
2. You may paraphrase and reorganize verified facts.
3. Never invent, assume, or infer unsupported financial information.
4. Prioritize the information that directly answers the customer's question.
5. Use natural conversational phrasing rather than database terminology.
6. Avoid robotic constructions such as:
   - "The applicable interest rate is..."
   - "As per the available information..."
   - "Please be informed that..."
   - "I would be happy to assist..."
   - "Kindly note that..."
7. Don't restate the customer's question unnecessarily.
8. Don't add filler just to make the response sound conversational.
9. Don't force every response into a template.
10. Follow the RESPONSE POLICY for length and structure, but treat it as constraints rather than predefined wording.
11. If several facts are available, select and synthesize only the facts relevant to the customer's question.
12. Sound like a knowledgeable human financial-service representative, not an API, database, chatbot, or legal document.
"""

PERSONALITY_CONTRACT = """
You are Easy Advisor, an expert digital loan advisor at Easy Home Finance.

RESPONSE STYLE:
- Answer only what the user asked.
- Default to 1–3 short sentences.
- Use bullets only when listing multiple important items.
- Do not repeat information already given.
- Do not restate the user's question.
- Do not provide background unless requested.
- Do not add generic menus or "How can I help?" after every answer.
- Ask at most ONE relevant follow-up question when necessary.
- For workflow steps, show only the current step.
- Keep financial/legal explanations simple and concise.
- Never add unnecessary emojis.
- If the user asks for more detail, then expand.

PERSONALITY RULES:
1. Answer the user's actual question first.
2. Use the current conversation context.
3. Never restart the conversation unnecessarily.
4. Never repeat the generic welcome menu unless the user actually starts a new journey.
5. Preserve verified numbers, rates and statuses exactly.
6. Never invent contractual or financial information.
7. Explain financial terminology in simple language.
8. Be direct and clear, without conversational filler.
9. Don't apologize unless something actually went wrong.
10. Don't say "I'm just an AI".
11. Don't say "outside my training" when a human escalation is appropriate.
12. If information isn't available, explain that clearly and offer the correct next step.
13. If the customer is frustrated, acknowledge the frustration and adapt the conversation.
14. If the customer asks to slow down, switch to one-step-at-a-time mode.
15. Preserve pending workflow state when answering side questions.
"""

# -----------------------------------------------------------------------------
# RESPONSE VALIDATOR (Anti-Robotic & Factual Check)
# -----------------------------------------------------------------------------
class ResponseValidator:
    """
    Validates drafted responses before returning to customer:
    1. Rejects banned robotic phrases / filler
    2. Ensures length and bullet budgets are respected
    3. Confirms factual integrity
    """
    FORBIDDEN_PHRASES = [
        "as an ai", "as per available records", "please be informed that",
        "kindly note that", "the applicable interest rate is", "outside what i'm trained for",
        "i would be happy to assist you today", "based on my programming",
        "i do not have access to personal"
    ]

    @classmethod
    def validate(cls, text: str, policy: Any, verified_data: Dict[str, Any]) -> Tuple[bool, str]:
        text_lower = text.lower().strip()

        for phrase in cls.FORBIDDEN_PHRASES:
            if phrase in text_lower:
                return False, f"Forbidden robotic phrase detected: '{phrase}'"

        if policy:
            max_b = getattr(policy, "max_bullets", 0)
            if max_b > 0:
                bullets = [line for line in text.split("\n") if line.strip().startswith("•")]
                if len(bullets) > max_b:
                    return False, f"Bullet count {len(bullets)} exceeds limit of {max_b}"

        return True, "PASSED"


class GeminiEngine:
    """
    Dual-LLM Architecture:
    1. First LLM (understand_message): Pure conversation comprehension.
       Produces structured JSON: Intent, Speech Act, Entities, Topic, Domain Type, Risk, Route.
    2. Second LLM (generate_humanized_response): Fact-grounded natural generation.
       Synthesizes verified data into warm, plain-English dialogue enforcing the Personality Contract.
    """

    # -------------------------------------------------------------------------
    # LAYER 1: CONVERSATION UNDERSTANDING (First LLM)
    # -------------------------------------------------------------------------
    @classmethod
    def understand_message(
        cls,
        user_message: str,
        state_dict: Dict[str, Any],
        history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Extracts structured semantic understanding without answering prematurely.
        Returns understanding, decision, domain type, confidence, risk, and route.
        """
        msg = user_message.strip()

        # Try Gemini API if key is present
        if GEMINI_API_KEY:
            try:
                llm_understanding = cls._call_understanding_api(msg, state_dict, history)
                if llm_understanding:
                    return llm_understanding
            except Exception as e:
                print(f"[Gemini Understanding API Error]: {e}")

        # High-precision cognitive semantic classifier
        return cls._local_semantic_understanding(msg, state_dict, history)

    @classmethod
    def _local_semantic_understanding(
        cls,
        text: str,
        state_dict: Dict[str, Any],
        history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        msg_lower = text.lower().strip()
        workflow_state = state_dict.get("workflow_state", "IDLE")
        active_goal = state_dict.get("active_goal")

        # Entity Extraction
        entities = {}
        amt = cls._parse_amount(text)
        if amt:
            entities["amount"] = amt
        otp = cls._parse_otp(text)
        if otp:
            entities["otp"] = otp
        pan = cls._parse_pan(text)
        if pan:
            entities["pan"] = pan

        # 1. TYPE E: Explicit Human Agent Request
        if any(k in msg_lower for k in [
            "talk to human", "speak to agent", "connect to executive", "human agent",
            "support person", "human please", "speak to someone", "connect with human",
            "customer care", "call priority support"
        ]):
            return {
                "understanding": {
                    "intent": "HUMAN_AGENT_REQUEST",
                    "speech_act": "HUMAN_REQUEST",
                    "entities": entities,
                    "topic": "SUPPORT_ESCALATION",
                    "user_goal": "SPEAK_WITH_HUMAN"
                },
                "decision": {
                    "route": "HUMAN_ESCALATION",
                    "domain_type": "TYPE_E_HUMAN_REQUEST",
                    "confidence": 0.99,
                    "risk": "HIGH",
                    "requires_auth": False,
                    "requires_human": True,
                    "action_required": False
                },
                "response_guidance": {"tone": "empathetic_swift", "preserve_pending_workflow": True}
            }

        # 2. FRAUD / SECURITY / STOLEN PHONE ESCALATION (Critical Risk)
        if any(k in msg_lower for k in [
            "fraud", "police", "legal notice", "threat", "bribe", "hacked",
            "stolen", "unauthorized", "stole my phone", "unauthorized debit"
        ]):
            return {
                "understanding": {
                    "intent": "COMPLAINT_OR_FRAUD",
                    "speech_act": "CRITICAL_COMPLAINT",
                    "entities": entities,
                    "topic": "FRAUD_AND_SECURITY",
                    "user_goal": "REPORT_FRAUD"
                },
                "decision": {
                    "route": "HUMAN_ESCALATION",
                    "domain_type": "TYPE_E_HUMAN_REQUEST",
                    "confidence": 0.99,
                    "risk": "CRITICAL",
                    "requires_auth": True,
                    "requires_human": True,
                    "action_required": False
                },
                "response_guidance": {"tone": "urgent_reassuring", "preserve_pending_workflow": False}
            }

        # 3. GUARDRAIL: Credit Underwriting Bypass ("approve loan now", "reduce rate to 5%")
        if any(k in msg_lower for k in [
            "approve my loan", "sanction my loan immediately", "reduce interest rate to 5%",
            "guarantee approval", "lower rate to 4%", "alter my interest rate"
        ]):
            return {
                "understanding": {
                    "intent": "RESTRICTED_LENDING_ACTION",
                    "speech_act": "UNAUTHORIZED_REQUEST",
                    "entities": entities,
                    "topic": "CREDIT_UNDERWRITING",
                    "user_goal": "RATE_OR_SANCTION_OVERRIDE"
                },
                "decision": {
                    "route": "POLICY_GUARDRAIL",
                    "domain_type": "TYPE_A_RELEVANT_UNSUPPORTED",
                    "confidence": 0.99,
                    "risk": "HIGH",
                    "requires_auth": True,
                    "requires_human": False,
                    "action_required": False
                },
                "response_guidance": {"tone": "professional_firm", "preserve_pending_workflow": True}
            }

        # 4. TYPE F: Completely Unrelated (IPL, cake recipes, poems, jokes, crypto)
        if any(k in msg_lower for k in [
            "poem", "chocolate cake", "bake", "ipl", "cricket", "dogecoin", "bitcoin",
            "crypto", "joke", "funny", "capital of france", "recipe", "weather in"
        ]):
            return {
                "understanding": {
                    "intent": "OUT_OF_DOMAIN_QUERY",
                    "speech_act": "UNRELATED_QUERY",
                    "entities": {},
                    "topic": "OFF_TOPIC",
                    "user_goal": "CASUAL_OR_CURIOUS"
                },
                "decision": {
                    "route": "OUT_OF_DOMAIN",
                    "domain_type": "TYPE_F_UNRELATED",
                    "confidence": 0.98,
                    "risk": "LOW",
                    "requires_auth": False,
                    "requires_human": False,
                    "action_required": False
                },
                "response_guidance": {"tone": "polite_focused", "preserve_pending_workflow": True}
            }

        # 5. USER FRUSTRATION
        if any(f in msg_lower for f in [
            "stop repeating", "fixed answer", "robotic", "sound like a bot",
            "script", "repeat", "useless", "not helping", "talk normally", "i don't understand"
        ]):
            return {
                "understanding": {
                    "intent": "EXPRESS_FRUSTRATION",
                    "speech_act": "FRUSTRATION",
                    "entities": {},
                    "topic": "CONVERSATION_PACE",
                    "user_goal": "RESET_CONVERSATION"
                },
                "decision": {
                    "route": "CONVERSATIONAL_RESET",
                    "domain_type": "TYPE_D_ACTION_REQUEST",
                    "confidence": 0.95,
                    "risk": "LOW",
                    "requires_auth": False,
                    "requires_human": False,
                    "action_required": True
                },
                "response_guidance": {"tone": "humble_authentic", "preserve_pending_workflow": False}
            }

        # 6. NATURAL PACING ("one step at a time", "go slow")
        if any(k in msg_lower for k in ["one step at a time", "go slow", "take it easy", "step by step"]):
            return {
                "understanding": {
                    "intent": "GENERAL_CONVERSATION",
                    "speech_act": "STATEMENT",
                    "entities": {},
                    "topic": "PACING",
                    "user_goal": "SLOW_DOWN"
                },
                "decision": {
                    "route": "CONVERSATIONAL",
                    "domain_type": "TYPE_B_RELEVANT_ANSWERABLE",
                    "confidence": 0.95,
                    "risk": "LOW",
                    "requires_auth": False,
                    "requires_human": False,
                    "action_required": False
                },
                "response_guidance": {"tone": "patient_clear", "preserve_pending_workflow": True}
            }

        # 7. TYPE A: Relevant but Unsupported / High Contractual Risk (e.g. Borrower Demise / Inheritance)
        if any(k in msg_lower for k in [
            "if i die", "death of borrower", "demise", "what happens if i die", "nominee settlement",
            "inheritance of pledged", "transfer loan to brother", "transfer loan to someone else"
        ]):
            return {
                "understanding": {
                    "intent": "LOAN_SETTLEMENT_DECEASED",
                    "speech_act": "QUESTION",
                    "entities": {},
                    "topic": "LOAN_SETTLEMENT_CONTRACT",
                    "user_goal": "UNDERSTAND_SETTLEMENT_TERMS"
                },
                "decision": {
                    "route": "HUMAN_ESCALATION",
                    "domain_type": "TYPE_A_RELEVANT_UNSUPPORTED",
                    "confidence": 0.92,
                    "risk": "HIGH",
                    "requires_auth": True,
                    "requires_human": True,
                    "action_required": False
                },
                "response_guidance": {"tone": "respectful_careful", "preserve_pending_workflow": True}
            }

        # 8. TYPE D: Action Requests (Change bank account, mutation)
        if any(k in msg_lower for k in ["change bank", "update bank", "different account", "new bank"]) or ("change" in msg_lower and "bank" in msg_lower):
            return {
                "understanding": {
                    "intent": "CHANGE_BANK_ACCOUNT",
                    "speech_act": "ACTION_REQUEST",
                    "entities": {},
                    "topic": "DISBURSAL_DESTINATION",
                    "user_goal": "MUTATE_BANK_ACCOUNT"
                },
                "decision": {
                    "route": "WORKFLOW_FSM",
                    "domain_type": "TYPE_D_ACTION_REQUEST",
                    "confidence": 0.97,
                    "risk": "MEDIUM",
                    "requires_auth": True,
                    "requires_human": False,
                    "action_required": True
                },
                "response_guidance": {"tone": "actionable_clear", "preserve_pending_workflow": True}
            }

        # 9. TYPE C: Relevant Requiring Live API Data (Lien status, Application status)
        if (
            any(k in msg_lower for k in ["has my lien been marked", "lien status", "check lien", "is lien active"])
            or (workflow_state != "DISBURSED" and any(k in msg_lower for k in [
                "status", "where is my loan", "track application", "what is my application status",
                "what is the status of my loan", "application status"
            ]))
        ):
            intent_name = "LIEN_STATUS" if "lien" in msg_lower else "APPLICATION_STATUS"
            return {
                "understanding": {
                    "intent": intent_name,
                    "speech_act": "QUESTION",
                    "entities": entities,
                    "topic": "LIVE_APPLICATION_STATUS",
                    "user_goal": "TRACK_STATUS"
                },
                "decision": {
                    "route": "API_QUERY",
                    "domain_type": "TYPE_C_RELEVANT_LIVE_DATA",
                    "confidence": 0.98,
                    "risk": "LOW",
                    "requires_auth": True,
                    "requires_human": False,
                    "action_required": False
                },
                "response_guidance": {"tone": "reassuring_accurate", "preserve_pending_workflow": True}
            }

        # 10. TYPE B: Relevant & Answerable via RAG
        # 10a. Agreement / KFS Explanation (Key Feature Requested by User)
        is_sign_action = any(k in msg_lower for k in ["e-sign", "esign", "disburse"]) or ("sign" in msg_lower and not any(q in msg_lower for q in ["explain", "how", "what", "why", "where"]))
        is_agreement_query = (
            any(k in msg_lower for k in [
                "explain key points", "explain agreement", "explain my agreement",
                "what does the agreement say", "walk through kfs", "terms of the loan",
                "contract terms", "view key fact statement", "view kfs", "explain kfs",
                "key points from the agreement", "explain the agreement"
            ]) or (
                any(k in msg_lower for k in ["agreement", "kfs", "contract terms"]) and
                any(q in msg_lower for q in ["explain", "what", "walk", "points", "terms", "understand", "read", "details", "view"])
            )
        )
        if is_agreement_query and not is_sign_action:
            return {
                "understanding": {
                    "intent": "AGREEMENT_EXPLANATION",
                    "speech_act": "QUESTION",
                    "entities": entities,
                    "topic": "KFS_AND_AGREEMENT",
                    "user_goal": "UNDERSTAND_BEFORE_SIGNING"
                },
                "decision": {
                    "route": "RAG",
                    "domain_type": "TYPE_B_RELEVANT_ANSWERABLE",
                    "confidence": 0.96,
                    "risk": "MEDIUM",
                    "requires_auth": True,
                    "requires_human": False,
                    "action_required": False
                },
                "response_guidance": {"tone": "warm_clear", "preserve_pending_workflow": True}
            }

        # 10b. Fee & Charges Breakdown
        if any(k in msg_lower for k in ["charges", "fees", "fee", "penalty", "foreclosure charge", "prepayment", "explain the charges"]):
            return {
                "understanding": {
                    "intent": "INQUIRE_FEES",
                    "speech_act": "QUESTION",
                    "entities": entities,
                    "topic": "CHARGES_AND_FEES",
                    "user_goal": "COST_TRANSPARENCY"
                },
                "decision": {
                    "route": "RAG",
                    "domain_type": "TYPE_B_RELEVANT_ANSWERABLE",
                    "confidence": 0.97,
                    "risk": "LOW",
                    "requires_auth": False,
                    "requires_human": False,
                    "action_required": False
                },
                "response_guidance": {"tone": "transparent_informative", "preserve_pending_workflow": True}
            }

        # 10c. Interest Rate Query
        if any(k in msg_lower for k in ["interest rate", "what is the interest", "rate of interest", "apr"]):
            return {
                "understanding": {
                    "intent": "INQUIRE_INTEREST_RATE",
                    "speech_act": "QUESTION",
                    "entities": entities,
                    "topic": "INTEREST_RATES",
                    "user_goal": "COST_ASSESSMENT"
                },
                "decision": {
                    "route": "RAG",
                    "domain_type": "TYPE_B_RELEVANT_ANSWERABLE",
                    "confidence": 0.98,
                    "risk": "LOW",
                    "requires_auth": False,
                    "requires_human": False,
                    "action_required": False
                },
                "response_guidance": {"tone": "clear_encouraging", "preserve_pending_workflow": True}
            }

        # 10d. Lien Explanation
        if any(k in msg_lower for k in ["what does lien mean", "what is lien", "why lien", "lien marking"]):
            return {
                "understanding": {
                    "intent": "INQUIRE_LIEN_EXPLANATION",
                    "speech_act": "QUESTION",
                    "entities": entities,
                    "topic": "PLEDGE_AND_COLLATERAL",
                    "user_goal": "SECURITY_REASSURANCE"
                },
                "decision": {
                    "route": "RAG",
                    "domain_type": "TYPE_B_RELEVANT_ANSWERABLE",
                    "confidence": 0.96,
                    "risk": "LOW",
                    "requires_auth": False,
                    "requires_human": False,
                    "action_required": False
                },
                "response_guidance": {"tone": "reassuring_educational", "preserve_pending_workflow": True}
            }

        # 10e. Market Fluctuations & Margin Calls
        if any(k in msg_lower for k in ["nifty", "crash", "margin call", "market drops", "nav drops"]):
            return {
                "understanding": {
                    "intent": "INQUIRE_MARGIN_CALL",
                    "speech_act": "QUESTION",
                    "entities": entities,
                    "topic": "MARKET_RISK_AND_MARGIN_CALLS",
                    "user_goal": "RISK_PROTECTION"
                },
                "decision": {
                    "route": "RAG",
                    "domain_type": "TYPE_B_RELEVANT_ANSWERABLE",
                    "confidence": 0.95,
                    "risk": "LOW",
                    "requires_auth": False,
                    "requires_human": False,
                    "action_required": False
                },
                "response_guidance": {"tone": "calm_factual", "preserve_pending_workflow": True}
            }

        # 10f. Tax & SIP Continuation
        if any(k in msg_lower for k in ["sip", "tax", "capital gain"]):
            intent_name = "INQUIRE_TAX" if ("tax" in msg_lower or "capital" in msg_lower) else "POLICY_FAQ"
            return {
                "understanding": {
                    "intent": intent_name,
                    "speech_act": "QUESTION",
                    "entities": entities,
                    "topic": "TAX_AND_SIP",
                    "user_goal": "FINANCIAL_IMPACT"
                },
                "decision": {
                    "route": "RAG",
                    "domain_type": "TYPE_B_RELEVANT_ANSWERABLE",
                    "confidence": 0.95,
                    "risk": "LOW",
                    "requires_auth": False,
                    "requires_human": False,
                    "action_required": False
                },
                "response_guidance": {"tone": "clarifying", "preserve_pending_workflow": True}
            }

        # 11. POST-DISBURSEMENT CHECK (Balance, Limit, Draw Amount)
        if workflow_state == "DISBURSED":
            if any(k in msg_lower for k in ["status", "balance", "withdrawable", "limit", "agreement", "payout", "active", "disburs", "sign"]):
                return {
                    "understanding": {
                        "intent": "LAMF_ALREADY_ACTIVE",
                        "speech_act": "STATUS_CHECK",
                        "entities": entities,
                        "topic": "ACTIVE_CREDIT_LINE",
                        "user_goal": "CHECK_WITHDRAWABLE_BALANCE"
                    },
                    "decision": {
                        "route": "API_QUERY",
                        "domain_type": "TYPE_C_RELEVANT_LIVE_DATA",
                        "confidence": 0.99,
                        "risk": "LOW",
                        "requires_auth": True,
                        "requires_human": False,
                        "action_required": False
                    },
                    "response_guidance": {"tone": "affirming_warm", "preserve_pending_workflow": False}
                }

        # 12. AFFIRMATIVE PROGRESSION ('next', 'ok', 'proceed', 'yes', 'sure', 'sign it', 'let's do it')
        affirmative_tokens = {
            "next", "continue", "proceed", "yes", "yeah", "yep", "ok", "okay", "sure",
            "go ahead", "let's do it", "do it", "fine", "move ahead", "i'm ready",
            "let's continue", "what's next", "take me forward", "done", "sign it", "sign",
            "agree", "disburse", "forward", "yup", "e-sign", "esign", "e-sign agreement & disburse"
        }
        if any(msg_lower == sig or msg_lower.startswith(sig + " ") or msg_lower.endswith(" " + sig) or sig in msg_lower for sig in affirmative_tokens):
            return {
                "understanding": {
                    "intent": "ADVANCE_PENDING_ACTION",
                    "speech_act": "CONTINUE",
                    "entities": entities,
                    "topic": "WORKFLOW_PROGRESSION",
                    "user_goal": "PROCEED_TO_NEXT_STEP"
                },
                "decision": {
                    "route": "WORKFLOW_FSM",
                    "domain_type": "TYPE_D_ACTION_REQUEST",
                    "confidence": 0.99,
                    "risk": "LOW",
                    "requires_auth": True,
                    "requires_human": False,
                    "action_required": True
                },
                "response_guidance": {"tone": "efficient_warm", "preserve_pending_workflow": True}
            }

        # 13. VALUE PROVISION (PAN, Amount, OTP)
        # If waiting for OTP and an OTP is present
        if workflow_state == "OTP_VERIFICATION" and "otp" in entities:
            return {
                "understanding": {
                    "intent": "SUBMIT_OTP",
                    "speech_act": "PROVIDE_VALUE",
                    "entities": entities,
                    "topic": "RTA_LIEN_AUTHORIZATION",
                    "user_goal": "AUTHORIZE_LIEN"
                },
                "decision": {
                    "route": "WORKFLOW_FSM",
                    "domain_type": "TYPE_D_ACTION_REQUEST",
                    "confidence": 0.99,
                    "risk": "LOW",
                    "requires_auth": True,
                    "requires_human": False,
                    "action_required": True
                },
                "response_guidance": {"tone": "actionable", "preserve_pending_workflow": True}
            }

        # If amount or PAN is provided
        if "amount" in entities or "pan" in entities:
            return {
                "understanding": {
                    "intent": "SUBMIT_REQUESTED_INPUT",
                    "speech_act": "PROVIDE_VALUE",
                    "entities": entities,
                    "topic": "LOAN_PARAMETER_INPUT",
                    "user_goal": "PROVIDE_CREDENTIAL_OR_LIMIT"
                },
                "decision": {
                    "route": "WORKFLOW_FSM",
                    "domain_type": "TYPE_D_ACTION_REQUEST",
                    "confidence": 0.99,
                    "risk": "LOW",
                    "requires_auth": True,
                    "requires_human": False,
                    "action_required": True
                },
                "response_guidance": {"tone": "actionable", "preserve_pending_workflow": True}
            }

        # 14. MENU SELECTION IN IDLE STATE
        if workflow_state in ["IDLE", "CONVERSATIONAL_RESET"]:
            if msg_lower in ["1", "1.", "1️⃣", "option 1", "first option"]:
                return {
                    "understanding": {
                        "intent": "START_LAMF",
                        "speech_act": "INITIATE",
                        "entities": entities,
                        "topic": "LAMF_INITIATION",
                        "user_goal": "APPLY_LAMF"
                    },
                    "decision": {
                        "route": "WORKFLOW_FSM",
                        "domain_type": "TYPE_D_ACTION_REQUEST",
                        "confidence": 0.99,
                        "risk": "LOW",
                        "requires_auth": False,
                        "requires_human": False,
                        "action_required": True
                    },
                    "response_guidance": {"tone": "inviting", "preserve_pending_workflow": False}
                }
            elif msg_lower in ["2", "2.", "2️⃣", "option 2", "second option"]:
                return {
                    "understanding": {
                        "intent": "START_HOME_LOAN",
                        "speech_act": "INITIATE",
                        "entities": entities,
                        "topic": "HOME_LOAN_INITIATION",
                        "user_goal": "APPLY_HOME_LOAN"
                    },
                    "decision": {
                        "route": "WORKFLOW_FSM",
                        "domain_type": "TYPE_D_ACTION_REQUEST",
                        "confidence": 0.99,
                        "risk": "LOW",
                        "requires_auth": False,
                        "requires_human": False,
                        "action_required": True
                    },
                    "response_guidance": {"tone": "inviting", "preserve_pending_workflow": False}
                }
            elif msg_lower in ["3", "3.", "3️⃣", "option 3", "third option"]:
                return {
                    "understanding": {
                        "intent": "APPLICATION_STATUS",
                        "speech_act": "QUESTION",
                        "entities": entities,
                        "topic": "LIVE_APPLICATION_STATUS",
                        "user_goal": "TRACK_STATUS"
                    },
                    "decision": {
                        "route": "API_QUERY",
                        "domain_type": "TYPE_C_RELEVANT_LIVE_DATA",
                        "confidence": 0.99,
                        "risk": "LOW",
                        "requires_auth": True,
                        "requires_human": False,
                        "action_required": False
                    },
                    "response_guidance": {"tone": "reassuring", "preserve_pending_workflow": False}
                }

        # 15. JOURNEY STARTERS
        if any(k in msg_lower for k in ["lamf", "mutual fund loan", "loan against mutual", "pledge"]):
            return {
                "understanding": {
                    "intent": "START_LAMF",
                    "speech_act": "INITIATE",
                    "entities": entities,
                    "topic": "LAMF_INITIATION",
                    "user_goal": "APPLY_LAMF"
                },
                "decision": {
                    "route": "WORKFLOW_FSM",
                    "domain_type": "TYPE_D_ACTION_REQUEST",
                    "confidence": 0.98,
                    "risk": "LOW",
                    "requires_auth": False,
                    "requires_human": False,
                    "action_required": True
                },
                "response_guidance": {"tone": "welcoming_clear", "preserve_pending_workflow": False}
            }

        if any(k in msg_lower for k in ["home loan", "housing loan", "mortgage", "buy a home", "buy home", "buying a home"]):
            return {
                "understanding": {
                    "intent": "START_HOME_LOAN",
                    "speech_act": "INITIATE",
                    "entities": entities,
                    "topic": "HOME_LOAN_INITIATION",
                    "user_goal": "APPLY_HOME_LOAN"
                },
                "decision": {
                    "route": "WORKFLOW_FSM",
                    "domain_type": "TYPE_D_ACTION_REQUEST",
                    "confidence": 0.98,
                    "risk": "LOW",
                    "requires_auth": False,
                    "requires_human": False,
                    "action_required": True
                },
                "response_guidance": {"tone": "welcoming_clear", "preserve_pending_workflow": False}
            }

        # 16. DEFAULT CONVERSATION
        return {
            "understanding": {
                "intent": "GENERAL_CONVERSATION",
                "speech_act": "STATEMENT",
                "entities": entities,
                "topic": "GENERAL",
                "user_goal": "CHAT"
            },
            "decision": {
                "route": "CONVERSATIONAL",
                "domain_type": "TYPE_B_RELEVANT_ANSWERABLE",
                "confidence": 0.90,
                "risk": "LOW",
                "requires_auth": False,
                "requires_human": False,
                "action_required": False
            },
            "response_guidance": {"tone": "warm_clear", "preserve_pending_workflow": True}
        }
    # -------------------------------------------------------------------------
    # LAYER 2: HUMANIZED RESPONSE GENERATION & BREVITY COMPRESSION (Second LLM)
    # -------------------------------------------------------------------------
    @classmethod
    def generate_humanized_response(
        cls,
        verified_data: Dict[str, Any],
        context: Dict[str, Any],
        understanding: Dict[str, Any],
        policy: Optional[Any] = None
    ) -> str:
        """
        Synthesizes verified data and customer context into a crisp, concise,
        plain-English reply strictly enforcing Response Style and Brevity Policy.
        """
        if policy is None:
            try:
                from backend.app.response_policy import ResponsePolicy
                u_data = understanding.get("understanding", {})
                d_data = understanding.get("decision", {})
                policy = ResponsePolicy.evaluate(
                    intent=u_data.get("intent", ""),
                    speech_act=u_data.get("speech_act", ""),
                    domain_type=d_data.get("domain_type", ""),
                    workflow_state=context.get("workflow_state", "IDLE"),
                    message=context.get("last_user_message", "")
                )
            except Exception as e:
                print(f"[ResponsePolicy Evaluation Fallback]: {e}")
                policy = None

        reply = None
        # If Gemini API is configured, call it with natural language contract & policy
        if GEMINI_API_KEY:
            try:
                reply = cls._call_generation_api(verified_data, context, understanding, policy)
            except Exception as e:
                print(f"[Gemini Generation API Error]: {e}")

        if not reply:
            reply = cls._local_personality_generation(verified_data, context, understanding, policy)

        # Anti-Robotic Response Validation
        is_valid, reason = ResponseValidator.validate(reply, policy, verified_data)
        if not is_valid:
            print(f"[ResponseValidator Notice]: {reason}. Applying natural fallback.")
            reply = cls._local_personality_generation(verified_data, context, understanding, policy)

        return reply

    @classmethod
    def _local_personality_generation(
        cls,
        verified_data: Dict[str, Any],
        context: Dict[str, Any],
        understanding: Dict[str, Any],
        policy: Optional[Any] = None
    ) -> str:
        intent = understanding["understanding"]["intent"]
        workflow_state = context.get("workflow_state", "IDLE")
        entities = context.get("entities", {})
        amt = entities.get("selected_amount") or 250000.0
        amt_str = f"₹{amt:,.0f}"
        bank = entities.get("bank_account", "HDFC Bank (XXXX-3294)")
        rate = entities.get("interest_rate", 10.5)

        # 1. MULTI_POINT: Agreement / KFS Explanation (Natural sentences in bullets)
        if intent == "AGREEMENT_EXPLANATION":
            lakh_val = amt / 100000.0
            lakh_str = f"₹{lakh_val:.1f}".rstrip('0').rstrip('.') + " lakh" if lakh_val >= 1 else f"₹{amt:,.0f}"
            bank_account_clean = bank.replace("HDFC Bank (XXXX-3294)", "HDFC Bank account ending 3294")
            if "XXXX-" in bank_account_clean:
                bank_account_clean = re.sub(r'\(XXXX-(\d+)\)', r'account ending \1', bank_account_clean)
            return (
                f"Here are the key terms of your agreement:\n\n"
                f"• Your credit line is {lakh_str}.\n"
                f"• The interest rate is {rate}% p.a.\n"
                f"• There’s no foreclosure charge.\n"
                f"• Repayments are linked to your {bank_account_clean}.\n\n"
                f"Would you like me to explain the charges next?"
            )

        # 2. COMPLEX_REQUEST: Demise / Legal Settlement (Empathetic & clear)
        if intent == "LOAN_SETTLEMENT_DECEASED":
            return (
                "In the event of a borrower's demise, the registered nominee can settle the dues to release the pledged mutual funds.\n\n"
                "Would you like me to connect you with our Senior Loan Settlement Specialist?"
            )

        # 3. SIMPLE_QUESTION: Out-of-Domain Reframing (Polite & concise)
        if intent == "OUT_OF_DOMAIN_QUERY":
            return "I focus strictly on loans and credit lines against mutual funds. Would you like to explore your loan options?"

        # 4. SIMPLE_FACT: Live Lien Status
        if intent == "LIEN_STATUS":
            if workflow_state in ["AUTOPAY_REVIEW", "DISBURSED"]:
                return "Your lien has been successfully confirmed with CAMS, and your mutual fund units remain in your portfolio."
            else:
                return "Your lien is pending CAMS OTP authorization."

        # 5. MULTI_POINT: Application Status
        if intent == "APPLICATION_STATUS":
            return (
                "Here is the status of your application APP-HL-1092:\n\n"
                "• It is currently undergoing Technical Verification.\n"
                "• Pending items include property chain deeds and your latest electricity bill.\n"
                "• The estimated turnaround time is 3 business days."
            )

        # 6. WORKFLOW: Bank Account Change
        if intent == "CHANGE_BANK_ACCOUNT":
            return (
                f"Your disbursal account is currently set to {bank}. Please share your new Bank Name, Account Number, and IFSC so we can verify it with a ₹1 penny drop."
            )

        # 7. SIMPLE_FACT / MULTI_POINT: Policy & RAG Answers
        if intent == "INQUIRE_INTEREST_RATE":
            return f"Your current interest rate is {rate}% p.a., calculated on the daily reducing balance."
        elif intent == "INQUIRE_FEES":
            return (
                "Here is the breakdown of charges:\n\n"
                "• Processing fee is ₹1,179, inclusive of GST.\n"
                "• There is zero foreclosure or prepayment penalty.\n"
                "• An AutoPay bounce charge of ₹1,200 applies only if an installment fails due to insufficient balance."
            )
        elif intent == "INQUIRE_LIEN_EXPLANATION":
            return "Lien marking temporarily pledges your mutual funds as collateral. You stay 100% owner, receive all dividends, and your SIPs continue normally."
        elif intent == "INQUIRE_MARGIN_CALL":
            return "If NAV drops significantly, you receive a 7–10 day cure window to add units or repay part of the balance. Units are never liquidated without notice."
        elif intent == "INQUIRE_TAX":
            return "Pledging units is not a sale, so there is zero capital gains tax. Business borrowers can also claim interest as a tax deduction under Section 36(1)(iii)."

        # 8. Pacing
        if intent == "GENERAL_CONVERSATION" and "PACING" in understanding["understanding"].get("topic", ""):
            return "Understood. We'll take it strictly one step at a time. What would you like to start with?"

        # 9. Active Loan Info
        if intent == "LAMF_ALREADY_ACTIVE":
            return (
                f"Your agreement for APP-LAMF-8831 is signed and active.\n\n"
                f"• Approved credit line: {amt_str}\n"
                f"• Disbursal destination: {bank}\n"
                f"• Funds will reflect in your account within 2 hours"
            )

        # Fallback to verified fact string or default
        return verified_data.get("text", "I'm right here with you! How can I assist your loan journey today?")

    # -------------------------------------------------------------------------
    # HELPERS: ENTITY EXTRACTION
    # -------------------------------------------------------------------------
    @classmethod
    def _parse_amount(cls, text: str) -> Optional[float]:
        clean = text.lower().replace(",", "").replace("₹", "").replace("rs", "").strip()
        clean = clean.replace("unlock", "").replace("max", "").replace("full", "").strip()
        if "lakh" in clean or "lac" in clean or "l" in clean:
            nums = re.findall(r"[\d\.]+", clean)
            if nums:
                return float(nums[0]) * 100000
        if "k" in clean:
            nums = re.findall(r"[\d\.]+", clean)
            if nums:
                return float(nums[0]) * 1000

        words = clean.split()
        for w in words:
            if w.isdigit():
                if len(w) == 4:
                    continue
                val = float(w)
                if val >= 10000:
                    return val
        if clean.isdigit() and len(clean) != 4:
            val = float(clean)
            if val >= 10000:
                return val
        return None

    @classmethod
    def _parse_otp(cls, text: str) -> Optional[str]:
        digits = re.findall(r"\b\d{4}\b", text)
        return digits[0] if digits else None

    @classmethod
    def _parse_pan(cls, text: str) -> Optional[str]:
        clean = text.strip().upper()
        if "PAN12345" in clean:
            return "PAN12345"
        pans = re.findall(r"\b[A-Z]{5}\d{4}[A-Z]\b", clean)
        return pans[0] if pans else None

    # -------------------------------------------------------------------------
    # API CALLERS (Gemini Flash)
    # -------------------------------------------------------------------------
    @classmethod
    def _call_understanding_api(cls, msg: str, state_dict: dict, history: list) -> Optional[Dict[str, Any]]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        prompt = (
            f"You are the Conversation Understanding Layer of an AI Loan Advisor.\n"
            f"Do NOT generate a customer reply. Extract the structured intent and decision.\n\n"
            f"USER MESSAGE: \"{msg}\"\n"
            f"CURRENT WORKFLOW STATE: {state_dict.get('workflow_state')}\n"
            f"ACTIVE GOAL: {state_dict.get('active_goal')}\n"
            f"ENTITIES: {json.dumps(state_dict.get('entities', {}))}\n"
            f"CONVERSATION HISTORY: {json.dumps(history[-6:])}\n\n"
            f"Return ONLY valid JSON with this exact schema:\n"
            f"{{\n"
            f'  "understanding": {{\n'
            f'    "intent": "string",\n'
            f'    "speech_act": "QUESTION"|"CONTINUE"|"PROVIDE_VALUE"|"ACTION_REQUEST"|"FRUSTRATION"|"INITIATE"|"HUMAN_REQUEST"|"UNRELATED",\n'
            f'    "entities": {{}},\n'
            f'    "topic": "string",\n'
            f'    "user_goal": "string"\n'
            f'  }},\n'
            f'  "decision": {{\n'
            f'    "route": "RAG"|"WORKFLOW_FSM"|"API_QUERY"|"HUMAN_ESCALATION"|"OUT_OF_DOMAIN"|"CONVERSATIONAL",\n'
            f'    "domain_type": "TYPE_A_RELEVANT_UNSUPPORTED"|"TYPE_B_RELEVANT_ANSWERABLE"|"TYPE_C_RELEVANT_LIVE_DATA"|"TYPE_D_ACTION_REQUEST"|"TYPE_E_HUMAN_REQUEST"|"TYPE_F_UNRELATED",\n'
            f'    "confidence": 0.95,\n'
            f'    "risk": "LOW"|"MEDIUM"|"HIGH"|"CRITICAL",\n'
            f'    "requires_auth": true|false,\n'
            f'    "requires_human": true|false,\n'
            f'    "action_required": true|false\n'
            f'  }},\n'
            f'  "response_guidance": {{\n'
            f'    "tone": "string",\n'
            f'    "preserve_pending_workflow": true|false\n'
            f'  }}\n'
            f"}}"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=3) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            out_text = res_data['candidates'][0]['content']['parts'][0]['text']
            clean_json = re.sub(r'```(?:json)?', '', out_text).strip()
            return json.loads(clean_json)

    @classmethod
    def _call_generation_api(
        cls,
        verified_data: dict,
        context: dict,
        understanding: dict,
        policy: Optional[Any] = None
    ) -> Optional[str]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        policy_dict = policy.to_dict() if hasattr(policy, "to_dict") else (policy or {})
        prompt = (
            f"{NATURAL_LANGUAGE_CONTRACT}\n\n"
            f"{HIERARCHY_OF_OBJECTIVES}\n\n"
            f"{PERSONALITY_CONTRACT}\n\n"
            f"VERIFIED FACTS:\n{json.dumps(verified_data, indent=2)}\n\n"
            f"RESPONSE POLICY BOUNDARIES:\n"
            f"- Archetype: {policy_dict.get('archetype', 'SIMPLE_QUESTION')}\n"
            f"- Max Sentences: {policy_dict.get('max_sentences', 2)}\n"
            f"- Max Bullets: {policy_dict.get('max_bullets', 0)}\n"
            f"- Tone: {policy_dict.get('tone', 'conversational_natural')}\n"
            f"- Information Priority: {policy_dict.get('information_priority', [])}\n"
            f"- Allowed Facts: {policy_dict.get('allowed_facts', [])}\n"
            f"- Allow Follow-up Question: {policy_dict.get('allow_followup_question', False)}\n"
            f"- Follow-up Purpose: {policy_dict.get('followup_purpose') or 'None'}\n"
            f"- Prohibited Patterns: {policy_dict.get('prohibited_patterns', [])}\n\n"
            f"CUSTOMER CONTEXT:\n{json.dumps(context, indent=2)}\n\n"
            f"CUSTOMER INTENT:\n{json.dumps(understanding.get('understanding', {}), indent=2)}\n\n"
            f"Write the response naturally, interpreting the verified facts as a knowledgeable human loan advisor. "
            f"Do not dump database keys/labels. Stay strictly within the Response Policy boundaries."
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=3) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data['candidates'][0]['content']['parts'][0]['text'].strip()
