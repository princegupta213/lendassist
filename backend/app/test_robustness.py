import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.server import process_chat_message

def test_robustness():
    print("=" * 75)
    print("🔬 ADVANCED CONVERSATIONAL ROBUSTNESS & INTERRUPTIONS TEST")
    print("=" * 75)

    # TEST A: 10 Different Ways to Say "Continue" at e-Sign Step
    continuation_variants = [
        "next", "proceed", "continue", "yes", "sure", "ok", "okay",
        "go ahead", "let's do it", "sign it"
    ]

    print("\n1. Testing 10 Natural Phrasings for Affirmative Progression:")
    for idx, var in enumerate(continuation_variants, 1):
        s_id = f"test_progression_{idx}"
        # Advance to AUTOPAY_REVIEW
        process_chat_message({"message": "PAN12345", "conversation_id": s_id})
        process_chat_message({"message": "250000", "conversation_id": s_id})
        process_chat_message({"message": "9032", "conversation_id": s_id})
        
        # Test the variation
        res = process_chat_message({"message": var, "conversation_id": s_id})
        is_disbursed = res.get("intent") == "LAMF_DISBURSEMENT_COMPLETE"
        status = "✅ PASS" if is_disbursed else f"❌ FAIL ({res.get('intent')})"
        print(f"   [{idx:02d}/10] User: '{var}' -> {status}")

    # TEST B: Conversational Interruption & Seamless Resumption
    print("\n2. Testing Mid-Workflow Questions & Seamless Resumption:")
    s_id_interrupt = "test_interruption_session"
    process_chat_message({"message": "PAN12345", "conversation_id": s_id_interrupt})
    process_chat_message({"message": "250000", "conversation_id": s_id_interrupt})
    process_chat_message({"message": "9032", "conversation_id": s_id_interrupt})

    # At e-Sign stage, user asks: "wait what is the interest rate?"
    res_q = process_chat_message({"message": "wait, what is the interest rate?", "conversation_id": s_id_interrupt})
    print(f"   [Interruption] User: 'wait, what is the interest rate?'")
    print(f"   [Intent]: {res_q.get('intent')}")
    print(f"   [Bot snippet]: {res_q.get('response')[:140]}...")
    
    # User now says: "ok continue"
    res_c = process_chat_message({"message": "ok continue", "conversation_id": s_id_interrupt})
    print(f"\n   [Resumption] User: 'ok continue'")
    print(f"   [Intent]: {res_c.get('intent')}")
    print(f"   [Bot snippet]: {res_c.get('response')[:140]}...")

    # User clicks 'e-Sign Agreement & Disburse' AGAIN after completion
    res_repeat = process_chat_message({"message": "e-Sign Agreement & Disburse", "conversation_id": s_id_interrupt})
    print(f"\n   [Post-Disbursement Repeat] User: 'e-Sign Agreement & Disburse'")
    print(f"   [Intent]: {res_repeat.get('intent')}")
    print(f"   [Bot snippet]: {res_repeat.get('response')[:140]}...")

if __name__ == "__main__":
    test_robustness()
