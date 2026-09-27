"""
Escalation Engine for LendAssist — AI Lending Conversation Orchestration Layer.

Escalation is treated as a first-class product decision system that detects when
continuing with AI creates unacceptable customer, financial, compliance, or experience risk.

Formula:
  Escalation Score = Risk Score + Explicit Request + Repeated Failure + Uncertainty + Frustration + Workflow Failure
"""

import time
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict, field

@dataclass
class EscalationFactors:
    risk_score: float = 0.0             # 0.0 - 0.40 (Fraud, demise, legal, dispute)
    explicit_request: float = 0.0       # 0.0 or 0.85 ("talk to human", "speak to agent")
    repeated_failure: float = 0.0       # 0.0 - 0.30 (failed attempts, verification retries)
    ai_uncertainty: float = 0.0         # 0.0 - 0.25 (low model confidence < 0.70)
    customer_frustration: float = 0.0   # 0.0 - 0.25 (sentiment cues)
    workflow_failure: float = 0.0       # 0.0 - 0.35 (API failure, timeout, penny drop failure)

    def total_score(self) -> float:
        raw = (self.risk_score + self.explicit_request + self.repeated_failure +
               self.ai_uncertainty + self.customer_frustration + self.workflow_failure)
        return min(1.0, round(raw, 2))

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class AgentHandoffPacket:
    ticket_id: str
    timestamp: str
    priority: str                       # P1_CRITICAL, P2_HIGH, P3_MEDIUM, P4_LOW
    escalation_level: str               # LEVEL_0_AI, LEVEL_1_MONITORED, LEVEL_2_ASSISTED, LEVEL_3_PRIORITY
    escalation_score: float
    
    # Customer Info
    customer: Dict[str, Any]
    
    # Conversation Summary
    conversation: Dict[str, Any]
    
    # Problem Diagnosis
    problem: Dict[str, Any]
    
    # System & API Context
    system_context: Dict[str, Any]
    
    # AI Recommendation for Human Agent
    ai_recommendation: Dict[str, Any]
    
    # Customer's Last Stated Message
    customer_last_message: str
    status: str = "OPEN"                # OPEN, IN_PROGRESS, RESOLVED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EscalationDecisionSystem:
    """
    Evaluates multi-factor signals to determine whether an interaction should
    be ANSWERED by AI, ACTED upon via API, or ESCALATED to a human specialist.
    """

    FRUSTRATION_PATTERNS = [
        r'\b(?:this isn\'t helping|not helping|useless|stupid bot|terrible service)\b',
        r'\b(?:already told you|stop repeating|i told you before|waste of time)\b',
        r'\b(?:fed up|ridiculous|worst experience|speak to a real person)\b'
    ]

    HIGH_RISK_INTENTS = {
        "FRAUD_ESCALATION": (0.80, "P1_CRITICAL", "Grievance & Fraud Desk"),
        "UNAUTHORIZED_TRANSACTION": (0.80, "P1_CRITICAL", "Fraud Risk Operations"),
        "LEGAL_NOTICE": (0.75, "P1_CRITICAL", "Legal & Compliance Desk"),
        "LOAN_SETTLEMENT_DECEASED": (0.55, "P2_HIGH", "Senior Loan Settlement Specialist"),
        "DISPUTED_CHARGES": (0.50, "P2_HIGH", "Billing & Grievance Desk"),
        "FINANCIAL_HARDSHIP": (0.50, "P2_HIGH", "Restructuring & Collections Desk")
    }

    @classmethod
    def evaluate(
        cls,
        message: str,
        intent: str,
        confidence: float,
        context: Dict[str, Any],
        simulated_overrides: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, EscalationFactors, Optional[AgentHandoffPacket]]:
        """
        Returns:
          decision: "ANSWER" | "ACT" | "ESCALATE"
          factors: EscalationFactors
          handoff_packet: Optional[AgentHandoffPacket]
        """
        msg_lower = message.lower().strip()
        sim = simulated_overrides or {}
        factors = EscalationFactors()

        # 1. Evaluate Risk Score
        if intent in cls.HIGH_RISK_INTENTS:
            risk_weight, _, _ = cls.HIGH_RISK_INTENTS[intent]
            factors.risk_score = risk_weight
        elif any(k in msg_lower for k in ["stole", "stolen", "fraud", "hacked", "police", "unauthorized"]):
            factors.risk_score = 0.80
        elif any(k in msg_lower for k in ["die", "death", "deceased", "nominee transmission"]):
            factors.risk_score = 0.55
        elif sim.get("fraud_scenario"):
            factors.risk_score = 0.80

        # 2. Evaluate Explicit Request (0.0 or 0.85)
        human_patterns = [
            r'\b(?:connect|talk|speak)\s+(?:me\s+)?(?:to\s+|with\s+)?(?:an?\s+)?(?:agent|human|person|executive|representative|specialist|someone|somebody|customer\s+care|customer\s+support)\b',
            r'\b(?:i\s+want\s+(?:a\s+)?human|i\s+want\s+customer\s+support|let\s+me\s+speak|call\s+support|human\s+agent|real\s+person|customer\s+care|support\s+person)\b'
        ]
        is_explicit = (
            intent in ["HUMAN_HANDOFF", "TALK_TO_AGENT", "HUMAN_AGENT_REQUEST"] or
            sim.get("explicit_human_request") or
            any(re.search(pat, msg_lower) for pat in human_patterns) or
            any(kw in msg_lower for kw in [
                "connect with an agent", "connect with agent", "connect me with an agent",
                "speak to agent", "talk to human", "connect to agent", "representative",
                "talk to someone", "i want a human", "call support", "customer care", "customer support"
            ])
        )
        if is_explicit:
            factors.explicit_request = 0.85

        # 3. Evaluate Repeated Failures (0.0 to 0.30)
        failure_count = context.get("failed_attempts", 0)
        if sim.get("repeated_failures"):
            failure_count = max(failure_count, sim.get("repeated_failures"))
        if any(k in msg_lower for k in ["failed again", "tried this three times", "tried three times"]):
            failure_count = max(failure_count, 2)
        if failure_count >= 3:
            factors.repeated_failure = 0.30
        elif failure_count == 2:
            factors.repeated_failure = 0.20
        elif failure_count == 1:
            factors.repeated_failure = 0.10

        # 4. Evaluate AI Uncertainty (0.0 to 0.25)
        eff_confidence = sim.get("forced_confidence", confidence)
        if eff_confidence < 0.60:
            factors.ai_uncertainty = 0.25
        elif eff_confidence < 0.75:
            factors.ai_uncertainty = 0.15

        # 5. Evaluate Customer Frustration (0.0 to 0.25)
        is_frustrated = any(re.search(pat, msg_lower) for pat in cls.FRUSTRATION_PATTERNS)
        if is_frustrated or sim.get("customer_frustration"):
            factors.customer_frustration = 0.25

        # 6. Evaluate Workflow / API Failure (0.0 to 0.35)
        if (
            intent in ["BANK_VERIFICATION_FAILURE", "KYC_FAILURE", "RTA_TIMEOUT"] or
            context.get("api_error") or
            sim.get("api_failure") or
            sim.get("kyc_failure") or
            sim.get("rta_timeout") or
            any(k in msg_lower for k in [
                "penny drop verification failed", "penny drop failed", "my penny drop failed",
                "bank verification isn't working", "account verification failed", "the bank check failed"
            ])
        ):
            factors.workflow_failure = 0.35

        # Calculate Total Escalation Score (0.0 to 1.0)
        score = factors.total_score()

        # Determine Escalation Level
        if score >= 0.70:
            escalation_level = "LEVEL_3_PRIORITY"
            decision = "ESCALATE"
        elif score >= 0.50:
            escalation_level = "LEVEL_2_ASSISTED"
            decision = "ESCALATE"
        elif score >= 0.30:
            escalation_level = "LEVEL_1_MONITORED"
            decision = "ANSWER"
        else:
            escalation_level = "LEVEL_0_AI"
            decision = "ACT" if context.get("workflow_state") in ["PORTFOLIO_REVIEW", "OTP_VERIFICATION", "AUTOPAY_REVIEW"] else "ANSWER"

        # Construct Agent Handoff Packet if escalated
        handoff_packet = None
        if decision == "ESCALATE":
            handoff_packet = cls._create_agent_handoff_packet(
                message=message,
                intent=intent,
                score=score,
                level=escalation_level,
                factors=factors,
                context=context
            )

        return decision, factors, handoff_packet

    @classmethod
    def _create_agent_handoff_packet(
        cls,
        message: str,
        intent: str,
        score: float,
        level: str,
        factors: EscalationFactors,
        context: Dict[str, Any]
    ) -> AgentHandoffPacket:
        ticket_num = int(time.time() * 1000) % 100000
        ticket_id = f"TICK-LA-{ticket_num}"
        timestamp = time.strftime("%H:%M:%S")
        
        # Priority mapping
        if factors.risk_score >= 0.35 or factors.explicit_request > 0.8:
            priority = "P1_CRITICAL"
        elif score >= 0.60:
            priority = "P2_HIGH"
        else:
            priority = "P3_MEDIUM"

        entities = context.get("entities", {})
        customer_name = entities.get("name", "Aryan Agarwal")
        app_id = entities.get("application_id", "APP-LAMF-8831")
        product = entities.get("product_type", "Loan Against Mutual Funds (LAMF)")
        bank = entities.get("bank_account", "HDFC Bank ending 3294")
        amt_val = entities.get('selected_amount')
        if amt_val is None:
            amt_val = 250000.0
        limit = f"₹{amt_val:,.0f}"

        # Diagnose Category & Reason
        category = "General Assistance"
        reason = "Customer requested human specialist."
        action_recommendation = "Review customer query and provide live assistance."
        
        if factors.risk_score >= 0.35:
            if "stole" in message.lower() or "fraud" in message.lower() or "unauthorized" in message.lower():
                category = "Unauthorized Activity & Fraud Alert"
                reason = "Customer reports unauthorized transaction or phone theft."
                action_recommendation = "1. Confirm identity. 2. Verify temporary loan lock & security freeze. 3. Initiate fraud investigation protocol."
            elif "die" in message.lower() or "death" in message.lower() or "deceased" in message.lower():
                category = "Borrower Demise & Transmission"
                reason = "Nominee transmission and pledge settlement inquiry."
                action_recommendation = "Verify legal heir credentials and explain transmission settlement timeline."
        elif factors.workflow_failure > 0:
            category = "Technical / API Disconnection"
            reason = "Automated verification failed or RTA gateway timed out."
            action_recommendation = "Manually check CAMS RTA or Bank Penny Drop portal and unblock application."
        elif factors.customer_frustration > 0:
            category = "Customer Experience Escalation"
            reason = "Customer expressed repeated frustration with digital self-service."
            action_recommendation = "Acknowledge inconvenience immediately and complete the pending step directly."

        # Summary of actions already attempted by AI
        actions_taken = [
            f"Active session identified for {customer_name} ({app_id})",
            f"Facility registered: {product} ({limit}) linked to {bank}",
            f"Escalation score computed: {score:.2f} [{level}]"
        ]
        if factors.risk_score >= 0.35:
            actions_taken.append("Account marked for security freeze / priority review")
        if factors.workflow_failure > 0:
            actions_taken.append("Automated API retry exhausted (attempt 3/3)")

        assigned_desk = "Senior Loan Advisory Desk"
        if intent in cls.HIGH_RISK_INTENTS:
            assigned_desk = cls.HIGH_RISK_INTENTS[intent][2]
        elif intent in ["HUMAN_HANDOFF", "TALK_TO_AGENT"]:
            assigned_desk = "Priority Support Desk"
        elif priority == "P1_CRITICAL":
            assigned_desk = "Priority Fraud Desk"
        elif factors.workflow_failure > 0:
            assigned_desk = "Technical Gateway Operations"

        return AgentHandoffPacket(
            ticket_id=ticket_id,
            timestamp=timestamp,
            priority=priority,
            escalation_level=level,
            escalation_score=score,
            customer={
                "customer_id": "CUST-9428",
                "name": customer_name,
                "application_id": app_id,
                "product": product,
                "phone_masked": "+91-98XXXX1234",
                "linked_bank": bank,
                "sanctioned_limit": limit
            },
            conversation={
                "turn_count": len(context.get("history", [])) // 2 + 1,
                "detected_intent": intent,
                "topic": context.get("active_goal", "LENDING_SERVICE"),
                "summary": f"Customer inquiring regarding {category.lower()}. AI reached threshold {score:.2f} triggering handoff."
            },
            problem={
                "category": category,
                "stated_issue": message,
                "contributing_factors": {
                    "risk": factors.risk_score,
                    "explicit_request": factors.explicit_request,
                    "repeated_failures": factors.repeated_failure,
                    "uncertainty": factors.ai_uncertainty,
                    "frustration": factors.customer_frustration,
                    "workflow_failure": factors.workflow_failure
                }
            },
            system_context={
                "workflow_state": context.get("workflow_state", "IDLE"),
                "actions_attempted": actions_taken,
                "gateway_status": "DEGRADED" if factors.workflow_failure > 0 else "OPERATIONAL"
            },
            ai_recommendation={
                "reason_for_escalation": reason,
                "suggested_agent_action": action_recommendation,
                "action_items": [action_recommendation],
                "assigned_desk": assigned_desk
            },
            customer_last_message=message,
            status="OPEN"
        )
