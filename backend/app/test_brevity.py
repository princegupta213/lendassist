import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.server import process_chat_message
from backend.app.response_policy import ResponsePolicy

def test_brevity_and_response_policy():
    print("=" * 75)
    print("📏 TESTING RESPONSE POLICY LAYER & ADAPTIVE BREVITY COMPRESSION")
    print("=" * 75)

    failures = []

    # 1. Test ResponsePolicy Classifier Directly
    p1 = ResponsePolicy.evaluate("INQUIRE_INTEREST_RATE", "QUESTION", "TYPE_B_RELEVANT_ANSWERABLE", "IDLE", "What's my interest rate?")
    print(f"\n1. Direct Policy Check: 'What's my interest rate?' -> Archetype: {p1.archetype}, Max Sentences: {p1.max_sentences}")
    if p1.archetype != "SIMPLE_FACT" or p1.max_sentences != 1:
        failures.append(f"Expected SIMPLE_FACT with 1 sentence, got {p1.archetype} ({p1.max_sentences})")

    p2 = ResponsePolicy.evaluate("AGREEMENT_EXPLANATION", "QUESTION", "TYPE_B_RELEVANT_ANSWERABLE", "AUTOPAY_REVIEW", "explain key points from the agreement")
    print(f"2. Direct Policy Check: 'explain key points from the agreement' -> Archetype: {p2.archetype}, Max Bullets: {p2.max_bullets}")
    if p2.archetype != "MULTI_POINT" or p2.max_bullets != 4:
        failures.append(f"Expected MULTI_POINT with 4 bullets, got {p2.archetype} ({p2.max_bullets})")

    p3 = ResponsePolicy.evaluate("LOAN_SETTLEMENT_DECEASED", "QUESTION", "TYPE_A_RELEVANT_UNSUPPORTED", "IDLE", "What happens if I die?")
    print(f"3. Direct Policy Check: 'What happens if I die?' -> Archetype: {p3.archetype}, Follow-up: {p3.followup_question}")
    if p3.archetype != "COMPLEX_REQUEST":
        failures.append(f"Expected COMPLEX_REQUEST, got {p3.archetype}")

    # 2. End-to-End Chat Brevity Tests
    session_id = "test_brevity_session_01"

    # Journey setup to e-sign
    process_chat_message({"message": "Apply for LAMF", "conversation_id": session_id})
    process_chat_message({"message": "PAN12345", "conversation_id": session_id})
    process_chat_message({"message": "290000", "conversation_id": session_id})
    process_chat_message({"message": "9032", "conversation_id": session_id})

    # Test A: Agreement Key Points (Target format: 4 bullets + 'Want me to explain the charges too?')
    print("\n--- Test A: 'explain key points from the agreement' ---")
    res_agree = process_chat_message({"message": "explain key points from the agreement", "conversation_id": session_id})
    resp_agree = res_agree.get("response", "")
    print("Bot Response:\n" + resp_agree)

    # Assertions
    bullets = [line for line in resp_agree.split("\n") if line.strip().startswith("•")]
    print(f"-> Bullet count: {len(bullets)} (Expected: 4)")
    if len(bullets) != 4:
        failures.append(f"Expected exactly 4 bullets in agreement explanation, got {len(bullets)}")
    if "explain the charges" not in resp_agree.lower():
        failures.append("Expected follow-up question offering charges explanation in agreement explanation")
    if "2.9" not in resp_agree and "290,000" not in resp_agree:
        failures.append("Expected 2.9L or 290,000 credit line in agreement explanation")
    if "HDFC" not in resp_agree:
        failures.append("Expected HDFC bank in agreement explanation")
    if "Credit line:" in resp_agree or "Foreclosure: Nil" in resp_agree:
        failures.append("Found robotic database label dumping in agreement explanation")
    if "Absolutely!" in resp_agree or "happy to walk you through" in resp_agree:
        failures.append("Found conversational filler in agreement explanation")

    # Test B: Simple Fact Rate Query ('what is the interest rate')
    print("\n--- Test B: 'what is the interest rate?' ---")
    res_rate = process_chat_message({"message": "what is the interest rate?", "conversation_id": session_id})
    resp_rate = res_rate.get("response", "")
    print("Bot Response:\n" + resp_rate)
    lines_rate = [l.strip() for l in resp_rate.split("\n") if l.strip()]
    print(f"-> Non-empty lines count: {len(lines_rate)}")
    if "10.5% p.a." not in resp_rate:
        failures.append(f"Expected '10.5% p.a.' in interest rate response, got: {resp_rate}")
    if len(lines_rate) > 2:
        failures.append(f"Expected at most 2 lines for rate answer + resumption, got {len(lines_rate)}")

    # Test C: Off-Topic Brevity Query ('Who won the IPL match yesterday?')
    print("\n--- Test C: 'Who won the IPL match yesterday?' ---")
    res_ipl = process_chat_message({"message": "Who won the IPL match yesterday?", "conversation_id": session_id})
    resp_ipl = res_ipl.get("response", "")
    print("Bot Response:\n" + resp_ipl)
    if len(resp_ipl.split("\n\n")) > 2 or len(resp_ipl) > 160:
        failures.append(f"Off-topic response is too long ({len(resp_ipl)} chars): {resp_ipl}")
    if "outside what I'm trained for" in resp_ipl or "I am just an AI" in resp_ipl:
        failures.append(f"Found cliché in off-topic response: {resp_ipl}")

    # Test D: Demise Contractual Policy ('What happens if I die while the loan is active?')
    print("\n--- Test D: 'What happens if I die while the loan is active?' ---")
    s_demise = "test_brevity_demise"
    res_demise = process_chat_message({"message": "What happens if I die while the loan is active?", "conversation_id": s_demise})
    resp_demise = res_demise.get("response", "")
    print("Bot Response:\n" + resp_demise)
    if "Senior Loan Settlement Specialist" not in resp_demise:
        failures.append("Specialist escalation missing from demise response")
    if len(resp_demise.split("\n\n")) > 2:
        failures.append("Demise response should be brief (1 statement + 1 question)")

    print("\n" + "=" * 75)
    if failures:
        print(f"❌ BREVITY TEST FAILED ({len(failures)} errors):")
        for f in failures:
            print(f"   - {f}")
        sys.exit(1)
    else:
        print("🏆 ALL RESPONSE POLICY & BREVITY TESTS PASSED WITH 100% SUCCESS!")
        print("=" * 75)

if __name__ == "__main__":
    test_brevity_and_response_policy()
