"""
Comprehensive Automated Test Suite for LendAssist Escalation Engine & Decision System.
Validates:
1. Multi-signal formula (Risk, Explicit, Failure, Uncertainty, Frustration, Workflow).
2. Four escalation tiers: LEVEL_0_AI, LEVEL_1_MONITORED, LEVEL_2_ASSISTED, LEVEL_3_PRIORITY.
3. Priority mapping (P1_CRITICAL, P2_HIGH, P3_MEDIUM, P4_LOW).
4. Full Agent Handoff Packet (Dossier, Diagnosis, AI Actions, Recommendations).
5. Server chat integration with simulation overrides and escalation analysis metadata.
"""

import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.escalation_engine import EscalationDecisionSystem, EscalationFactors, AgentHandoffPacket
from backend.app.server import process_chat_message, SUPPORT_TICKETS, ANALYTICS_DATA

def test_multi_factor_scoring():
    factors = EscalationFactors(
        risk_score=0.40,
        explicit_request=0.85,
        repeated_failure=0.20,
        ai_uncertainty=0.15,
        customer_frustration=0.25,
        workflow_failure=0.35
    )
    score = factors.total_score()
    assert score == 1.0, f"Expected capped at 1.0, got {score}"

    f2 = EscalationFactors(risk_score=0.10, ai_uncertainty=0.15)
    assert f2.total_score() == 0.25, f"Expected 0.25, got {f2.total_score()}"
    print("✅ test_multi_factor_scoring passed")

def test_autonomous_level_0():
    msg = "What is the interest rate on home loans?"
    decision, factors, packet = EscalationDecisionSystem.evaluate(
        message=msg,
        intent="FAQ_RAG",
        confidence=0.95,
        context={"entities": {"name": "Rahul Sharma", "application_id": "APP-HL-1092"}}
    )
    assert decision in ["ANSWER", "ACT"], f"Expected ANSWER/ACT, got {decision}"
    assert packet is None, "Autonomous level should not generate a handoff packet"
    assert factors.total_score() < 0.30, f"Expected score < 0.30, got {factors.total_score()}"
    print("✅ test_autonomous_level_0 passed")

def test_monitored_level_1():
    msg = "Is there any charge if I prepay part of my home loan?"
    # Ambiguous / lower confidence scenario
    decision, factors, packet = EscalationDecisionSystem.evaluate(
        message=msg,
        intent="FAQ_RAG",
        confidence=0.55,  # triggers ai_uncertainty 0.25 + maybe 0.10 failure = 0.35
        context={"failed_attempts": 1}
    )
    assert decision == "ANSWER", f"Expected ANSWER for monitored, got {decision}"
    assert packet is None, "Monitored level should not escalate immediately"
    assert 0.30 <= factors.total_score() < 0.50, f"Expected 0.30 <= score < 0.50, got {factors.total_score()}"
    print("✅ test_monitored_level_1 passed")

def test_assisted_level_2_workflow_failure():
    # Customer experienced an RTA / API timeout in LAMF
    msg = "The pledge OTP is not coming from CAMS, it says gateway timeout"
    decision, factors, packet = EscalationDecisionSystem.evaluate(
        message=msg,
        intent="LAMF_WORKFLOW",
        confidence=0.90,
        context={
            "failed_attempts": 2, # repeated_failure 0.20
            "api_error": True,    # workflow_failure 0.35
            "entities": {
                "name": "Aryan Agarwal",
                "application_id": "APP-LAMF-8831",
                "product_type": "Loan Against Mutual Funds",
                "selected_amount": 250000.0
            }
        }
    )
    assert decision == "ESCALATE", f"Expected ESCALATE, got {decision}"
    assert packet is not None, "Assisted level must produce handoff packet"
    assert packet.escalation_level == "LEVEL_2_ASSISTED", f"Expected LEVEL_2_ASSISTED, got {packet.escalation_level}"
    assert packet.problem["category"] == "Technical / API Disconnection"
    print("✅ test_assisted_level_2_workflow_failure passed")

def test_priority_level_3_explicit_human():
    msg = "Please let me speak to a human agent right now"
    decision, factors, packet = EscalationDecisionSystem.evaluate(
        message=msg,
        intent="TALK_TO_AGENT",
        confidence=0.98,
        context={"entities": {"name": "Rahul Sharma", "application_id": "APP-HL-1092"}}
    )
    assert decision == "ESCALATE", f"Expected ESCALATE, got {decision}"
    assert packet is not None
    assert packet.escalation_level == "LEVEL_3_PRIORITY"
    assert packet.priority == "P1_CRITICAL"
    assert factors.explicit_request == 0.85
    print("✅ test_priority_level_3_explicit_human passed")

def test_priority_level_3_fraud_alert():
    msg = "My phone was stolen and someone is trying to do unauthorized transactions on my loan"
    decision, factors, packet = EscalationDecisionSystem.evaluate(
        message=msg,
        intent="FRAUD_ESCALATION",
        confidence=0.99,
        context={"entities": {"name": "Aryan Agarwal", "application_id": "APP-LAMF-8831"}}
    )
    assert decision == "ESCALATE", f"Expected ESCALATE, got {decision}"
    assert packet is not None
    assert packet.priority == "P1_CRITICAL"
    assert packet.ai_recommendation["assigned_desk"] == "Grievance & Fraud Desk"
    assert "security freeze" in packet.ai_recommendation["action_items"][0].lower() or "freeze" in packet.ai_recommendation["reason_for_escalation"].lower()
    print("✅ test_priority_level_3_fraud_alert passed")

def test_priority_level_3_deceased_borrower():
    msg = "The borrower has deceased, how does the nominee settle the loan?"
    decision, factors, packet = EscalationDecisionSystem.evaluate(
        message=msg,
        intent="LOAN_SETTLEMENT_DECEASED",
        confidence=0.98,
        context={"entities": {"name": "Rahul Sharma", "application_id": "APP-HL-1092"}}
    )
    assert decision == "ESCALATE", f"Expected ESCALATE, got {decision}"
    assert packet is not None
    assert packet.ai_recommendation["assigned_desk"] == "Senior Loan Settlement Specialist"
    print("✅ test_priority_level_3_deceased_borrower passed")

def test_customer_dossier_integrity():
    msg = "Connect me to an agent"
    _, _, packet = EscalationDecisionSystem.evaluate(
        message=msg,
        intent="TALK_TO_AGENT",
        confidence=0.95,
        context={
            "entities": {
                "name": "Aryan Agarwal",
                "application_id": "APP-LAMF-8831",
                "product_type": "Loan Against Mutual Funds (LAMF)",
                "bank_account": "HDFC Bank ending 3294",
                "selected_amount": 350000.0
            }
        }
    )
    dossier = packet.to_dict()
    # Check all required PM packet sections
    assert "ticket_id" in dossier
    assert "customer" in dossier
    assert dossier["customer"]["name"] == "Aryan Agarwal"
    assert dossier["customer"]["application_id"] == "APP-LAMF-8831"
    assert "conversation" in dossier
    assert "problem" in dossier
    assert "system_context" in dossier
    assert "ai_recommendation" in dossier
    assert len(dossier["ai_recommendation"]["action_items"]) > 0
    print("✅ test_customer_dossier_integrity passed")

def test_server_chat_escalation_integration():
    SUPPORT_TICKETS.clear()
    req = {
        "message": "Fraud on my account! Cancel everything!",
        "conversation_id": "test_sess_001",
        "auth_state": True,
        "app_id": "APP-HL-1092"
    }
    resp = process_chat_message(req)
    assert resp["basket"] == "BASKET_4_HUMAN_ESCALATION"
    assert "escalation_analysis" in resp
    assert resp["escalation_analysis"]["decision"] == "ESCALATE"
    assert resp["escalation_analysis"]["priority"] == "P1_CRITICAL"
    assert len(SUPPORT_TICKETS) > 0
    assert SUPPORT_TICKETS[0]["customer"]["application_id"] == "APP-HL-1092"
    print("✅ test_server_chat_escalation_integration passed")

def test_server_simulation_overrides():
    # Test simulation flag: kyc_failure + repeated_failures
    req = {
        "message": "My PAN upload isn't working",
        "conversation_id": "test_sess_002",
        "auth_state": True,
        "app_id": "APP-LAMF-8831",
        "simulation": {
            "kyc_failure": True,
            "repeated_failures": 3
        }
    }
    resp = process_chat_message(req)
    assert resp["basket"] == "BASKET_4_HUMAN_ESCALATION"
    assert resp["escalation_analysis"]["score"] >= 0.65
    print("✅ test_server_simulation_overrides passed")

def test_analytics_metrics_contract():
    assert "total_conversations" in ANALYTICS_DATA
    assert ANALYTICS_DATA["self_service_resolution_rate"] > 70.0
    assert ANALYTICS_DATA["escalation_rate"] < 20.0
    assert ANALYTICS_DATA["hallucination_rate"] < 0.5
    assert "strategy_a_metrics" in ANALYTICS_DATA
    assert "strategy_b_metrics" in ANALYTICS_DATA
    print("✅ test_analytics_metrics_contract passed")

if __name__ == "__main__":
    print("\n--- Running LendAssist Escalation Engine Test Suite ---")
    test_multi_factor_scoring()
    test_autonomous_level_0()
    test_monitored_level_1()
    test_assisted_level_2_workflow_failure()
    test_priority_level_3_explicit_human()
    test_priority_level_3_fraud_alert()
    test_priority_level_3_deceased_borrower()
    test_customer_dossier_integrity()
    test_server_chat_escalation_integration()
    test_server_simulation_overrides()
    test_analytics_metrics_contract()
    print("\n🎉 ALL 10 ESCALATION SYSTEM TESTS PASSED SUCCESSFULLY!\n")
