"""
Test Suite: V7 Conversational Orchestrator & State Machine Verification
Tests key production fixes:
1. "connect with an agent" -> HUMAN_HANDOFF immediate resolution without generic fallbacks
2. UI Actions ("Call Priority Support", "Return to Assistant") handled cleanly without conversational echoing
3. Context switching between APP-LAMF-8831 and APP-HL-1092
4. Adaptive workflow failure (Penny drop failure -> retry guidance -> second failure -> auto-escalation)
5. Workflow continuation ("try the verification again")
6. Emergency fraud escalation
7. Elimination of robotic filler
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.server import process_chat_message
from backend.app.cognitive_engine import DialogueManager


class TestV7Orchestrator(unittest.TestCase):
    def setUp(self):
        # Reset any session state
        DialogueManager.SESSIONS.clear()

    def test_explicit_human_handoff(self):
        """Verify that 'connect with an agent' maps to HUMAN_HANDOFF with the exact expected response."""
        req = {
            "conversation_id": "test_handoff_1",
            "message": "connect with an agent",
            "auth_state": True,
            "app_id": "APP-HL-1092"
        }
        res = process_chat_message(req)
        
        self.assertEqual(res.get("basket"), "BASKET_4_HUMAN_ESCALATION")
        self.assertEqual(res.get("intent"), "HUMAN_HANDOFF")
        self.assertIn("Absolutely. I’ll connect you with a support specialist", res.get("response", ""))
        self.assertNotIn("How would you like to proceed today?", res.get("response", ""))
        self.assertNotIn("I'm right here with you", res.get("response", ""))
        self.assertIn("ticket", res)
        self.assertEqual(res["ticket"]["ai_recommendation"]["assigned_desk"], "Priority Support Desk")

    def test_ui_action_normalization(self):
        """Verify that UI button clicks are intercepted as UI_ACTION and never echoed as customer chat."""
        # 1. Call Priority Support button
        req_call = {
            "conversation_id": "test_ui_1",
            "message": "Call Priority Support (1800-EASY-HL)",
            "auth_state": True
        }
        res_call = process_chat_message(req_call)
        self.assertEqual(res_call.get("intent"), "CALL_PRIORITY_SUPPORT")
        self.assertIn("1800-EASY-HL", res_call.get("response", ""))
        self.assertNotIn("You mentioned: 'Call Priority Support'", res_call.get("response", ""))

        # 2. Return to Assistant button
        req_return = {
            "conversation_id": "test_ui_1",
            "message": "Return to Assistant",
            "auth_state": True
        }
        res_return = process_chat_message(req_return)
        self.assertEqual(res_return.get("intent"), "RETURN_TO_ASSISTANT")
        self.assertIn("Welcome back", res_return.get("response", ""))

        # 3. View Agent Workspace
        req_dossier = {
            "conversation_id": "test_ui_1",
            "message": "View Agent Workspace",
            "auth_state": True
        }
        res_dossier = process_chat_message(req_dossier)
        self.assertEqual(res_dossier.get("intent"), "VIEW_AGENT_WORKSPACE")
        self.assertIn("Opening Agent Workspace Dossier", res_dossier.get("response", ""))

    def test_dynamic_context_switch(self):
        """Verify checking application status reflects the dynamically switched context."""
        # Set context to APP-LAMF-8831
        req_lamf = {
            "conversation_id": "test_ctx_1",
            "message": "Check Application Status",
            "auth_state": True,
            "app_id": "APP-LAMF-8831"
        }
        res_lamf = process_chat_message(req_lamf)
        resp_lamf = res_lamf.get("response", "")
        self.assertIn("APP-LAMF-8831", resp_lamf)
        self.assertNotIn("APP-HL-1092", resp_lamf)

        # Switch context to APP-HL-1092
        req_hl = {
            "conversation_id": "test_ctx_1",
            "message": "Check Application Status",
            "auth_state": True,
            "app_id": "APP-HL-1092"
        }
        res_hl = process_chat_message(req_hl)
        resp_hl = res_hl.get("response", "")
        self.assertIn("APP-HL-1092", resp_hl)
        self.assertNotIn("APP-LAMF-8831", resp_hl)

    def test_adaptive_workflow_failure_and_escalation(self):
        """
        Verify:
        Turn 1: Bank verification failure -> provides retry guidance (does NOT escalate yet).
        Turn 2: Retry request ("try the verification again") -> guides re-initiation.
        Turn 3: Repeated failure -> auto-escalates to Technical Gateway Operations.
        """
        session_id = "test_workflow_failure_seq"
        
        # Turn 1: First failure
        req1 = {
            "conversation_id": session_id,
            "message": "Penny drop verification failed for my bank account",
            "auth_state": True,
            "app_id": "APP-LAMF-8831"
        }
        res1 = process_chat_message(req1)
        self.assertNotEqual(res1.get("basket"), "BASKET_4_HUMAN_ESCALATION", "First attempt should offer retry, not immediate escalation")
        self.assertEqual(res1.get("intent"), "BANK_VERIFICATION_FAILURE")
        self.assertTrue(
            "bank verification" in res1.get("response", "").lower() or
            "penny drop" in res1.get("response", "").lower()
        )
        self.assertIn("retry", res1.get("response", "").lower())

        # Turn 2: Retry
        req2 = {
            "conversation_id": session_id,
            "message": "try the verification again",
            "auth_state": True,
            "app_id": "APP-LAMF-8831"
        }
        res2 = process_chat_message(req2)
        self.assertTrue(
            "re-initiating" in res2.get("response", "").lower() or
            "retry" in res2.get("response", "").lower()
        )

        # Turn 3: Second failure -> Should escalate!
        req3 = {
            "conversation_id": session_id,
            "message": "Penny drop verification failed for my bank account",
            "auth_state": True,
            "app_id": "APP-LAMF-8831"
        }
        res3 = process_chat_message(req3)
        self.assertEqual(res3.get("basket"), "BASKET_4_HUMAN_ESCALATION")
        self.assertIn("ticket", res3)
        self.assertIn("Technical Gateway Operations", res3.get("response", ""))
        self.assertIn("failed again", res3.get("response", "").lower())

    def test_fraud_escalation(self):
        """Verify fraud inquiries immediately trigger Priority 1 Fraud Desk escalation."""
        req = {
            "conversation_id": "test_fraud_1",
            "message": "someone took a loan using my account",
            "auth_state": True
        }
        res = process_chat_message(req)
        self.assertEqual(res.get("basket"), "BASKET_4_HUMAN_ESCALATION")
        self.assertIn("ticket", res)
        self.assertEqual(res["ticket"]["priority"], "P1_CRITICAL")
        self.assertEqual(res["ticket"]["ai_recommendation"]["assigned_desk"], "Grievance & Fraud Desk")


if __name__ == "__main__":
    unittest.main()
