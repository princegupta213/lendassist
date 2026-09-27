import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.server import process_chat_message

# Expanded 50+ Test Cases across 11 distinct user conversations
TEST_CONVERSATIONS = [
    # CHAT 1: Complete LAMF Happy Path with Numeric Inputs
    {
        "chat_id": "CHAT_01_LAMF_HAPPY_PATH",
        "description": "LAMF full application with raw numbers, affirmative progression, and post-sign inquiry",
        "turns": [
            ("Apply for LAMF", "LAMF_START"),
            ("PAN12345", "LAMF_PORTFOLIO_LOADED"),
            ("250000", "LAMF_OTP_SENT"),
            ("9032", "LAMF_AUTOPAY_REVIEW"),
            ("next", "LAMF_DISBURSEMENT_COMPLETE"),
            ("Check Withdrawable Balance", "LAMF_ALREADY_ACTIVE")
        ]
    },
    # CHAT 2: LAMF Exceeding Max Portfolio LTV
    {
        "chat_id": "CHAT_02_LAMF_LIMIT_EXCEEDED",
        "description": "User requests 400000 (exceeds 320000 limit), adjusts down, enters OTP",
        "turns": [
            ("apply loan against mutual funds", "LAMF_START"),
            ("PAN12345", "LAMF_PORTFOLIO_LOADED"),
            ("400000", "LAMF_AMOUNT_EXCEEDED"),
            ("Unlock Max ₹320,000", "LAMF_OTP_SENT"),
            ("Enter 9032", "LAMF_AUTOPAY_REVIEW"),
            ("e-Sign Agreement & Disburse", "LAMF_DISBURSEMENT_COMPLETE")
        ]
    },
    # CHAT 3: Natural Pacing ("one step at a time" & "go slow")
    {
        "chat_id": "CHAT_03_NATURAL_PACING",
        "description": "User asks to take it one step at a time, selects 1, enters PAN and amount",
        "turns": [
            ("hi", "GENERAL_CONVERSATION"),
            ("can we do one step at a time", "GENERAL_CONVERSATION"),
            ("1", "LAMF_START"),
            ("PAN12345", "LAMF_PORTFOLIO_LOADED"),
            ("150000", "LAMF_OTP_SENT"),
            ("9032", "LAMF_AUTOPAY_REVIEW")
        ]
    },
    # CHAT 4: Discursive Affirmations ("ok", "proceed", "yes", "sure")
    {
        "chat_id": "CHAT_04_DISCURSIVE_AFFIRMATIONS",
        "description": "User uses pragmatic short signals like 'ok', 'proceed', 'done'",
        "turns": [
            ("LAMF", "LAMF_START"),
            ("PAN12345", "LAMF_PORTFOLIO_LOADED"),
            ("200000", "LAMF_OTP_SENT"),
            ("9032", "LAMF_AUTOPAY_REVIEW"),
            ("proceed", "LAMF_DISBURSEMENT_COMPLETE"),
            ("status", "LAMF_ALREADY_ACTIVE")
        ]
    },
    # CHAT 5: Security & Fraud Escalation
    {
        "chat_id": "CHAT_05_FRAUD_ESCALATION",
        "description": "Unauthorized transaction flags immediate Tier 4 escalation",
        "turns": [
            ("Someone stole my phone and took a loan", "COMPLAINT_OR_FRAUD"),
            ("unauthorized debit from account", "COMPLAINT_OR_FRAUD"),
            ("Return to Assistant", "GENERAL_CONVERSATION")
        ]
    },
    # CHAT 6: Explicit Human Agent Request
    {
        "chat_id": "CHAT_06_HUMAN_AGENT_REQUEST",
        "description": "User demands human assistance directly",
        "turns": [
            ("Can I speak to a human agent please", "HUMAN_AGENT_REQUEST"),
            ("connect to executive", "HUMAN_AGENT_REQUEST"),
            ("Call Priority Support (1800-EASY-HL)", "GENERAL_CONVERSATION")
        ]
    },
    # CHAT 7: Credit Underwriting Guardrail (Bypass Attempt)
    {
        "chat_id": "CHAT_07_CREDIT_GUARDRAIL",
        "description": "User asks bot to approve loan or lower rate to 4%",
        "turns": [
            ("Can you approve my loan right now?", "RESTRICTED_LENDING_ACTION"),
            ("sanction my loan immediately", "RESTRICTED_LENDING_ACTION"),
            ("Reduce interest rate to 5% please", "RESTRICTED_LENDING_ACTION")
        ]
    },
    # CHAT 8: Live Status Lookup (LOS API Integration)
    {
        "chat_id": "CHAT_08_STATUS_LOOKUP",
        "description": "Authenticated real-time query against LOS for APP-HL-1092",
        "turns": [
            ("where is my loan", "APPLICATION_STATUS"),
            ("track application", "APPLICATION_STATUS"),
            ("what is my application status", "APPLICATION_STATUS"),
            ("what is the status of my loan", "APPLICATION_STATUS")
        ]
    },
    # CHAT 9: Home Loan Initiation Flow
    {
        "chat_id": "CHAT_09_HOME_LOAN_FLOW",
        "description": "User initiates home loan journey",
        "turns": [
            ("I want a home loan", "HOME_LOAN_START"),
            ("housing loan", "HOME_LOAN_START"),
            ("buy a home", "HOME_LOAN_START")
        ]
    },
    # CHAT 10: Off-Topic Queries Handled by Domain Guardrail
    {
        "chat_id": "CHAT_10_OFF_TOPIC_GUARD",
        "description": "Tests diverse off-topic queries to ensure polite reframing",
        "turns": [
            ("Write a poem about nature", "OUT_OF_DOMAIN_QUERY"),
            ("How to bake a chocolate cake", "OUT_OF_DOMAIN_QUERY"),
            ("Who won the IPL match yesterday?", "OUT_OF_DOMAIN_QUERY"),
            ("Can I get a loan against Dogecoin or Bitcoin?", "OUT_OF_DOMAIN_QUERY"),
            ("Tell me a funny joke", "OUT_OF_DOMAIN_QUERY"),
            ("What is the capital of France?", "OUT_OF_DOMAIN_QUERY")
        ]
    },
    # CHAT 11: Policy Inquiries & FAQ
    {
        "chat_id": "CHAT_11_POLICY_FAQS",
        "description": "Testing policy inquiries on margin calls, tax benefits, and charges",
        "turns": [
            ("What is the interest rate for LAMF?", "GENERAL_CONVERSATION"),
            ("What are the prepayment charges?", "GENERAL_CONVERSATION"),
            ("Is my SIP stopped when I pledge units?", "GENERAL_CONVERSATION"),
            ("What happens if Nifty crashes?", "GENERAL_CONVERSATION"),
            ("Do I have to pay capital gains tax?", "GENERAL_CONVERSATION")
        ]
    }
]

def run_all_tests():
    total_turns = 0
    passed_turns = 0
    failed_turns = 0
    failures = []

    print("=" * 75)
    print("🚀 EXECUTING 50+ TEST CASES ACROSS 11 INDEPENDENT SESSIONS")
    print("=" * 75)

    for chat_idx, chat in enumerate(TEST_CONVERSATIONS, 1):
        s_id = f"test_session_{chat['chat_id']}"
        print(f"\n📁 [{chat_idx}/{len(TEST_CONVERSATIONS)}] {chat['chat_id']}")
        print(f"   Description: {chat['description']}")

        for turn_idx, (user_msg, expected_intent) in enumerate(chat["turns"], 1):
            total_turns += 1
            res = process_chat_message({
                "message": user_msg,
                "conversation_id": s_id,
                "app_id": "APP-HL-1092",
                "auth_state": True
            })

            actual_intent = res.get("intent")
            basket = res.get("basket")
            is_pass = (
                (actual_intent == expected_intent) or 
                (expected_intent == "GENERAL_CONVERSATION" and basket in ["BASKET_1_FAQ_RAG", "BASKET_2_GUIDED_WORKFLOW"]) or
                (expected_intent == "COMPLAINT_OR_FRAUD" and actual_intent in ["COMPLAINT_OR_FRAUD", "FRAUD_ESCALATION"]) or
                (expected_intent == "HUMAN_AGENT_REQUEST" and actual_intent in ["HUMAN_AGENT_REQUEST", "TALK_TO_AGENT"])
            )

            if is_pass:
                passed_turns += 1
                status = "✅ PASS"
            else:
                failed_turns += 1
                status = f"❌ FAIL (Expected: {expected_intent}, Got: {actual_intent})"
                failures.append({
                    "chat_id": chat["chat_id"],
                    "turn": turn_idx,
                    "input": user_msg,
                    "expected": expected_intent,
                    "got": actual_intent,
                    "response": res.get("response")[:120]
                })

            print(f"   Turn {turn_idx}: \"{user_msg}\" -> {status}")

    print("\n" + "=" * 75)
    print(f"📊 SUMMARY: Total Turns Tested: {total_turns} | Passed: {passed_turns} | Failed: {failed_turns}")
    print(f"📈 Overall Reliability Score: {(passed_turns/total_turns)*100:.1f}%")
    print("=" * 75)

    if failures:
        print("\n⚠️ Failures detected:")
        for f in failures:
            print(f"- {f['chat_id']} Turn {f['turn']}: '{f['input']}' Expected {f['expected']}, got {f['got']}")
    else:
        print("\n🏆 ALL 50 TEST CASES PASSED WITH 100% ACCURACY!")

if __name__ == "__main__":
    run_all_tests()
