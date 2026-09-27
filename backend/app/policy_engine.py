from typing import Dict, Any, Tuple

class PolicyEngine:
    """
    Centralized Policy Engine for Easy Home Finance & LAMF.
    Enforces business rules, eligibility gates, risk thresholds, and SLA priorities.
    """

    @staticmethod
    def evaluate_unpledge(auth: bool, outstanding_balance: float, app_status: str) -> Tuple[bool, str]:
        """
        Policy: UNPLEDGE
        Condition: User must be authenticated, outstanding balance must be 0, and status ACTIVE.
        """
        if not auth:
            return False, "Authentication required to initiate unpledge request."
        if outstanding_balance > 0:
            return False, f"Cannot release pledge: An outstanding balance of ₹{outstanding_balance:,.2f} is pending. Please clear this to release units."
        if app_status != "ACTIVE":
            return False, f"Loan is currently in status '{app_status}'. Unpledge can only be processed on active closed accounts."
        return True, "Unpledge request approved. Lien release will reflect within 24 to 48 business hours."

    @staticmethod
    def evaluate_rta_otp_resend(attempts: int) -> Tuple[bool, str, str]:
        """
        Policy: RTA_OTP_RESEND
        Condition: Max 3 attempts before escalating to RTA operations desk.
        """
        if attempts < 3:
            remaining = 3 - attempts
            return True, f"OTP resent successfully. You have {remaining} attempt(s) remaining before security verification.", "NORMAL"
        return False, "You have exceeded the maximum allowed OTP attempts (3/3). For your security, this has been escalated to our RTA Operations Desk.", "ESCALATE_RTA"

    @staticmethod
    def evaluate_portfolio_eligibility(portfolio_value: float) -> Tuple[bool, str, float]:
        """
        Policy: PORTFOLIO_MINIMUM_CUTOFF
        Condition: Minimum ₹50,000 portfolio value; 50% standard equity LTV.
        """
        if portfolio_value < 50000:
            return False, f"Your approved portfolio value is ₹{portfolio_value:,.2f}. Easy Home Finance requires a minimum holding of ₹50,000 to unlock LAMF credit lines.", 0.0
        max_limit = portfolio_value * 0.50
        return True, f"Eligible for credit line up to ₹{max_limit:,.2f} (based on 50% equity LTV).", max_limit

    @staticmethod
    def compute_escalation_score(factors: Dict[str, Any]) -> Tuple[int, str]:
        """
        Smart Escalation Scoring Engine:
        Score >= 80 -> Immediate Escalation
        Score 50-79 -> Offer Agent Assistance
        Score < 50  -> Continue Self-Service AI
        """
        score = 0
        if factors.get("fraud_or_security"):
            score += 100
        if factors.get("user_requested_human"):
            score += 85
        if factors.get("repeated_failures", 0) >= 3:
            score += 60
        if factors.get("api_failure"):
            score += 30
        if factors.get("confidence", 1.0) < 0.70:
            score += 25
        if factors.get("customer_sentiment") == "FRUSTRATED":
            score += 20

        if score >= 80:
            action = "IMMEDIATE_ESCALATION"
        elif score >= 50:
            action = "OFFER_ASSISTANCE"
        else:
            action = "CONTINUE_AI"
            
        return score, action
