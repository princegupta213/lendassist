"""
Response Policy Layer (Boundary & Constraint Architecture).

Policy controls the boundaries -> LLM interprets the facts -> LLM writes naturally.
Not: Policy dictates the exact wording -> LLM fills the template.

Hierarchy of Objectives:
1. FACTUAL CORRECTNESS
2. ANSWER THE USER'S ACTUAL INTENT
3. NATURAL HUMAN COMMUNICATION
4. BREVITY (shortest natural answer that fully satisfies the user's intent)
5. POLICY/FORMAT COMPLIANCE
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field

@dataclass
class ResponsePolicyConfig:
    archetype: str                          # SIMPLE_FACT, SIMPLE_QUESTION, MULTI_POINT, WORKFLOW, etc.
    max_sentences: int                      # Length constraint (e.g. 1, 2)
    max_bullets: int                        # Bullet budget (e.g. 3-4, or 0)
    format_style: str                       # "sentence", "bullets", "step_action"
    tone: str                               # "conversational_natural", "reassuring", "direct_clear", "respectful_concise", "empathetic_swift"
    information_priority: List[str] = field(default_factory=list)
    allowed_facts: List[str] = field(default_factory=list)
    followup_purpose: Optional[str] = None  # Purpose of follow-up if appropriate
    allow_followup_question: bool = False
    prohibited_patterns: List[str] = field(default_factory=lambda: [
        "as an ai", "i would be happy to", "as per available records", "please be informed that",
        "kindly note that", "outside what i'm trained for", "the applicable interest rate is"
    ])
    next_action: Optional[str] = None
    allow_emojis: bool = False

    @property
    def followup_question(self) -> Optional[str]:
        return self.followup_purpose

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["followup_question"] = self.followup_purpose
        return d


class ResponsePolicy:
    """
    Evaluates customer intent and conversational context to establish
    pure boundary constraints (length budget, tone, priority, prohibitions)
    for the natural language generation layer.
    """

    @classmethod
    def evaluate(
        cls,
        intent: str,
        speech_act: str,
        domain_type: str,
        workflow_state: str,
        message: str = "",
        entities: Optional[Dict[str, Any]] = None
    ) -> ResponsePolicyConfig:
        if entities is None:
            entities = {}
        msg_lower = message.lower().strip()

        # 1. HUMAN_ESCALATION / COMPLAINT
        if domain_type == "TYPE_E_HUMAN_REQUEST" or intent in ["TALK_TO_AGENT", "FRAUD_ESCALATION"]:
            if any(k in msg_lower for k in ["stole", "fraud", "unauthorized", "stolen"]):
                return ResponsePolicyConfig(
                    archetype="COMPLAINT",
                    max_sentences=2,
                    max_bullets=0,
                    format_style="sentence",
                    tone="empathetic_swift",
                    information_priority=["immediate account freeze", "priority ticket creation"],
                    allowed_facts=["account security", "incident ticket", "investigation timeframe"],
                    allow_followup_question=False,
                    next_action="LOCK_AND_ESCALATE"
                )
            return ResponsePolicyConfig(
                archetype="HUMAN_ESCALATION",
                max_sentences=2,
                max_bullets=0,
                format_style="sentence",
                tone="professional_warm",
                information_priority=["priority desk contact", "loan specialist availability"],
                allowed_facts=["phone support", "advisor handoff"],
                allow_followup_question=False,
                next_action="CONNECT_AGENT"
            )

        # 2. TYPE_A: Complex Contractual / Demise
        if domain_type == "TYPE_A_RELEVANT_UNSUPPORTED" or intent == "LOAN_SETTLEMENT_DECEASED":
            return ResponsePolicyConfig(
                archetype="COMPLEX_REQUEST",
                max_sentences=2,
                max_bullets=0,
                format_style="sentence",
                tone="respectful_concise",
                information_priority=["nominee transmission right", "pledge release upon settlement"],
                allowed_facts=["nominee settlement", "legal heir rights", "insurance coverage", "specialist desk"],
                followup_purpose="Offer connection to Senior Loan Settlement Specialist",
                allow_followup_question=True,
                next_action="SPEAK_WITH_SPECIALIST"
            )

        # 3. TYPE_B: Agreement & KFS Explanation (MULTI_POINT)
        if intent == "AGREEMENT_EXPLANATION":
            return ResponsePolicyConfig(
                archetype="MULTI_POINT",
                max_sentences=2,
                max_bullets=4,
                format_style="bullets",
                tone="conversational_natural",
                information_priority=["credit line amount", "interest rate", "foreclosure charge", "linked bank account"],
                allowed_facts=["credit line", "interest rate", "foreclosure fee", "repayment bank account"],
                followup_purpose="Offer charges explanation",
                allow_followup_question=True,
                next_action="ESIGN_DISBURSE"
            )

        # 4. TYPE_B: Fee and Rate Inquiries
        if intent in ["INQUIRE_FEES", "INQUIRE_INTEREST_RATE"]:
            if any(k in msg_lower for k in ["what's my interest rate", "what is my interest rate", "my interest rate", "what is the rate", "interest rate", "rate of interest"]):
                return ResponsePolicyConfig(
                    archetype="SIMPLE_FACT",
                    max_sentences=1,
                    max_bullets=0,
                    format_style="sentence",
                    tone="conversational_natural",
                    information_priority=["annual percentage rate", "daily reducing calculation"],
                    allowed_facts=["10.5% p.a.", "daily reducing balance"],
                    allow_followup_question=False,
                    next_action=None
                )
            return ResponsePolicyConfig(
                archetype="MULTI_POINT",
                max_sentences=1,
                max_bullets=3,
                format_style="bullets",
                tone="direct_clear",
                information_priority=["processing fee", "foreclosure charge", "bounce charge"],
                allowed_facts=["processing fee ₹1,179", "zero foreclosure", "bounce fee ₹1,200"],
                allow_followup_question=False,
                next_action=None
            )

        # 5. TYPE_C: Live Data / Telemetry
        if domain_type == "TYPE_C_RELEVANT_LIVE_DATA" or intent in ["LIEN_STATUS", "APPLICATION_STATUS", "LAMF_ALREADY_ACTIVE"]:
            if intent == "LIEN_STATUS":
                return ResponsePolicyConfig(
                    archetype="SIMPLE_FACT",
                    max_sentences=2,
                    max_bullets=0,
                    format_style="sentence",
                    tone="reassuring_natural",
                    information_priority=["lien registration status with CAMS", "portfolio ownership retention"],
                    allowed_facts=["lien confirmed", "units remain in portfolio"],
                    followup_purpose="Ask if customer is ready to complete e-sign",
                    allow_followup_question=True,
                    next_action="ESIGN_DISBURSE"
                )
            if intent == "LAMF_ALREADY_ACTIVE":
                return ResponsePolicyConfig(
                    archetype="SIMPLE_QUESTION",
                    max_sentences=2,
                    max_bullets=3,
                    format_style="bullets",
                    tone="conversational_natural",
                    information_priority=["active status", "approved limit", "payout timeframe"],
                    allowed_facts=["APP-LAMF-8831 active", "credit limit", "disbursal within 2 hours"],
                    allow_followup_question=False,
                    next_action=None
                )
            app_id = entities.get("application_id") or entities.get("app_id") or "APP-HL-1092"
            if "LAMF" in str(app_id):
                allowed_facts = [str(app_id), "credit line ₹2,50,000", "CAMS lien active", "HDFC Bank ending 3294"]
            else:
                allowed_facts = [str(app_id), "Technical Verification", "property deeds", "3 business days"]
            return ResponsePolicyConfig(
                archetype="MULTI_POINT",
                max_sentences=1,
                max_bullets=3,
                format_style="bullets",
                tone="direct_clear",
                information_priority=["application stage", "pending items", "estimated TAT"],
                allowed_facts=allowed_facts,
                allow_followup_question=False,
                next_action=None
            )

        # 6. TYPE_D: Bank Account Mutation / Workflow
        if intent == "CHANGE_BANK_ACCOUNT":
            return ResponsePolicyConfig(
                archetype="WORKFLOW",
                max_sentences=2,
                max_bullets=0,
                format_style="sentence",
                tone="conversational_natural",
                information_priority=["current bank account on file", "required new account details for penny drop"],
                allowed_facts=["current bank", "new bank name", "account number", "IFSC", "penny drop"],
                allow_followup_question=False,
                next_action="COLLECT_BANK_DETAILS"
            )

        # 6B. HUMAN_HANDOFF Policy
        if intent in ["HUMAN_HANDOFF", "HUMAN_AGENT_REQUEST", "TALK_TO_AGENT"]:
            return ResponsePolicyConfig(
                archetype="ESCALATION",
                max_sentences=2,
                max_bullets=0,
                format_style="sentence",
                tone="empathetic_swift",
                information_priority=["acknowledgment of specialist handoff", "conversation context preserved"],
                allowed_facts=["support specialist", "share conversation", "no repetition"],
                allow_followup_question=False,
                next_action=None
            )

        # 6C. BANK_VERIFICATION_FAILURE Policy
        if intent == "BANK_VERIFICATION_FAILURE":
            return ResponsePolicyConfig(
                archetype="WORKFLOW_ERROR",
                max_sentences=2,
                max_bullets=0,
                format_style="sentence",
                tone="actionable_reassuring",
                information_priority=["verification status", "suggested retry or escalation"],
                allowed_facts=["bank verification", "account details", "IFSC", "retry"],
                allow_followup_question=False,
                next_action="RETRY_VERIFICATION"
            )

        # 6D. CLARIFICATION_REQUIRED Policy
        if intent == "CLARIFICATION_REQUIRED":
            return ResponsePolicyConfig(
                archetype="CLARIFICATION",
                max_sentences=2,
                max_bullets=0,
                format_style="sentence",
                tone="helpful_direct",
                information_priority=["clarification question"],
                allowed_facts=["clarification required"],
                allow_followup_question=True,
                next_action=None
            )

        if workflow_state in ["PORTFOLIO_REVIEW", "OTP_VERIFICATION", "AUTOPAY_REVIEW"]:
            return ResponsePolicyConfig(
                archetype="WORKFLOW",
                max_sentences=2,
                max_bullets=0,
                format_style="step_action",
                tone="conversational_natural",
                information_priority=["current step progress", "single immediate action required"],
                allowed_facts=["step progress", "next immediate action"],
                allow_followup_question=False,
                next_action="PROCEED_STEP"
            )

        # 7. TYPE_F: Out-of-Domain Reframing
        if domain_type == "TYPE_F_UNRELATED" or intent == "OUT_OF_DOMAIN_QUERY":
            return ResponsePolicyConfig(
                archetype="SIMPLE_QUESTION",
                max_sentences=2,
                max_bullets=0,
                format_style="sentence",
                tone="polite_natural",
                information_priority=["loan advisory focus", "invitation to explore loan options"],
                allowed_facts=["lending focus", "mutual fund loans", "home loans"],
                followup_purpose="Invite to check loan options",
                allow_followup_question=True,
                next_action="CHECK_LOAN"
            )

        # Default fallback: SIMPLE_QUESTION
        return ResponsePolicyConfig(
            archetype="SIMPLE_QUESTION",
            max_sentences=2,
            max_bullets=0,
            format_style="sentence",
            tone="conversational_natural",
            information_priority=["direct response to query"],
            allowed_facts=[],
            allow_followup_question=False,
            next_action=None
        )
