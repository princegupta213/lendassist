import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.server import process_chat_message

def test_ai_native_architecture():
    print("=" * 75)
    print("🧠 TESTING AI-NATIVE DUAL-LLM CONVERSATIONAL ARCHITECTURE")
    print("=" * 75)

    failures = []
    session_id = "test_ai_native_session_01"

    # 1. Setup LAMF Journey up to e-Sign (AUTOPAY_REVIEW)
    print("\n--- STEP 1: Progress LAMF Journey to AUTOPAY_REVIEW ---")
    r1 = process_chat_message({"message": "Apply for LAMF", "conversation_id": session_id})
    r2 = process_chat_message({"message": "PAN12345", "conversation_id": session_id})
    r3 = process_chat_message({"message": "290000", "conversation_id": session_id})
    r4 = process_chat_message({"message": "9032", "conversation_id": session_id})
    print("   Journey progressed to Step 4 (e-Sign & Disbursal)")
    assert r4.get("intent") == "LAMF_AUTOPAY_REVIEW", f"Failed at OTP: {r4}"

    # 2. TEST: Explain key points from the agreement
    print("\n--- STEP 2: Query: 'explain key points from the agreement' ---")
    q_msg = "explain key points from the agreement"
    res_agree = process_chat_message({"message": q_msg, "conversation_id": session_id})
    intent_agree = res_agree.get("intent")
    resp_text = res_agree.get("response", "")
    chips = res_agree.get("action_chips", [])

    print(f"   User: '{q_msg}'")
    print(f"   Detected Intent: {intent_agree}")
    print(f"   Action Chips: {chips}")
    print("   Bot Response:\n   " + resp_text.replace("\n", "\n   "))

    if intent_agree != "AGREEMENT_EXPLANATION":
        failures.append(f"Expected AGREEMENT_EXPLANATION, got {intent_agree}")
    if "290,000" not in resp_text and "2.9" not in resp_text:
        failures.append(f"Credit limit 290,000 missing from response: {resp_text}")
    if "10.5" not in resp_text:
        failures.append(f"Interest rate 10.5 missing from response: {resp_text}")
    if "HDFC Bank" not in resp_text:
        failures.append(f"Bank name missing from response: {resp_text}")
    if "e-Sign Agreement & Disburse" not in chips:
        failures.append(f"e-Sign action chip missing from chips: {chips}")

    # 3. TEST: Follow-up: 'yes, explain the charges'
    print("\n--- STEP 3: Follow-up: 'yes, explain the charges' ---")
    q_charges = "yes, explain the charges"
    res_charges = process_chat_message({"message": q_charges, "conversation_id": session_id})
    intent_charges = res_charges.get("intent")
    resp_charges = res_charges.get("response", "")
    chips_charges = res_charges.get("action_chips", [])

    print(f"   User: '{q_charges}'")
    print(f"   Detected Intent: {intent_charges}")
    print(f"   Action Chips: {chips_charges}")
    print("   Bot Response:\n   " + resp_charges.replace("\n", "\n   "))

    if intent_charges != "INQUIRE_FEES":
        failures.append(f"Expected INQUIRE_FEES, got {intent_charges}")
    if "1,179" not in resp_charges or ("1200" not in resp_charges and "1,200" not in resp_charges):
        failures.append(f"Charges breakdown missing from response: {resp_charges}")
    if "e-Sign Agreement & Disburse" not in chips_charges:
        failures.append(f"e-Sign action chip missing from charges chips: {chips_charges}")

    # 4. TEST: Affirmative continuation after interruption
    print("\n--- STEP 4: Resume e-Sign: 'ok proceed' ---")
    res_disburse = process_chat_message({"message": "ok proceed", "conversation_id": session_id})
    intent_disburse = res_disburse.get("intent")
    print("   User: 'ok proceed'")
    print(f"   Detected Intent: {intent_disburse}")
    print(f"   Bot Response Snippet: {res_disburse.get('response')[:120]}...")
    if intent_disburse != "LAMF_DISBURSEMENT_COMPLETE":
        failures.append(f"Expected LAMF_DISBURSEMENT_COMPLETE, got {intent_disburse}")

    # 5. TEST: Type A (Relevant Unsupported / Demise / Legal Settlement)
    print("\n--- STEP 5: Type A: 'What happens if I die while the loan is active?' ---")
    s_demise = "test_ai_native_session_demise"
    q_demise = "What happens if I die while the loan is active?"
    res_demise = process_chat_message({"message": q_demise, "conversation_id": s_demise})
    intent_demise = res_demise.get("intent")
    resp_demise = res_demise.get("response", "")
    chips_demise = res_demise.get("action_chips", [])

    print(f"   User: '{q_demise}'")
    print(f"   Detected Intent: {intent_demise}")
    print(f"   Action Chips: {chips_demise}")
    print("   Bot Response:\n   " + resp_demise.replace("\n", "\n   "))

    if intent_demise != "LOAN_SETTLEMENT_DECEASED":
        failures.append(f"Expected LOAN_SETTLEMENT_DECEASED, got {intent_demise}")
    if "Loan Settlement Specialist" not in resp_demise:
        failures.append(f"Specialist offer missing from demise response: {resp_demise}")

    # 6. TEST: Type C (Live Lien Status Query)
    print("\n--- STEP 6: Type C: 'Has my lien been marked?' ---")
    s_lien = "test_ai_native_session_lien"
    process_chat_message({"message": "PAN12345", "conversation_id": s_lien})
    process_chat_message({"message": "250000", "conversation_id": s_lien})
    process_chat_message({"message": "9032", "conversation_id": s_lien})

    q_lien = "Has my lien been marked?"
    res_lien = process_chat_message({"message": q_lien, "conversation_id": s_lien})
    intent_lien = res_lien.get("intent")
    resp_lien = res_lien.get("response", "")

    print(f"   User: '{q_lien}'")
    print(f"   Detected Intent: {intent_lien}")
    print("   Bot Response:\n   " + resp_lien.replace("\n", "\n   "))

    if intent_lien != "LIEN_STATUS":
        failures.append(f"Expected LIEN_STATUS, got {intent_lien}")
    if "Confirmed" not in resp_lien and "CAMS" not in resp_lien:
        failures.append(f"Lien confirmation missing: {resp_lien}")

    # 7. TEST: Type D (Action Request: Change Bank Account)
    print("\n--- STEP 7: Type D: 'Change my bank account' ---")
    s_bank = "test_ai_native_session_bank"
    process_chat_message({"message": "PAN12345", "conversation_id": s_bank})
    process_chat_message({"message": "250000", "conversation_id": s_bank})
    process_chat_message({"message": "9032", "conversation_id": s_bank})

    q_bank = "Change my bank account"
    res_bank = process_chat_message({"message": q_bank, "conversation_id": s_bank})
    intent_bank = res_bank.get("intent")
    resp_bank = res_bank.get("response", "")
    chips_bank = res_bank.get("action_chips", [])

    print(f"   User: '{q_bank}'")
    print(f"   Detected Intent: {intent_bank}")
    print(f"   Action Chips: {chips_bank}")
    print("   Bot Response:\n   " + resp_bank.replace("\n", "\n   "))

    if intent_bank != "CHANGE_BANK_ACCOUNT":
        failures.append(f"Expected CHANGE_BANK_ACCOUNT, got {intent_bank}")
    if "penny drop" not in resp_bank.lower() and "ifsc" not in resp_bank.lower():
        failures.append(f"Bank verification instructions missing: {resp_bank}")

    # 8. TEST: Type F (Focused Reframing without cliches)
    print("\n--- STEP 8: Type F: 'Who won yesterday ipl match?' ---")
    s_ipl = "test_ai_native_session_ipl"
    q_ipl = "Who won yesterday ipl match?"
    res_ipl = process_chat_message({"message": q_ipl, "conversation_id": s_ipl})
    intent_ipl = res_ipl.get("intent")
    resp_ipl = res_ipl.get("response", "")

    print(f"   User: '{q_ipl}'")
    print(f"   Detected Intent: {intent_ipl}")
    print("   Bot Response:\n   " + resp_ipl.replace("\n", "\n   "))

    if intent_ipl != "OUT_OF_DOMAIN_QUERY":
        failures.append(f"Expected OUT_OF_DOMAIN_QUERY, got {intent_ipl}")
    if "outside what I'm trained for" in resp_ipl or "I'm just an AI" in resp_ipl:
        failures.append(f"Robotic cliche detected in response: {resp_ipl}")

    print("\n" + "=" * 75)
    if failures:
        print("FAILURES DETECTED:")
        for f in failures:
            print(f"  - {f}")
        assert False, f"{len(failures)} failures in AI-native tests."
    else:
        print("🏆 ALL AI-NATIVE ARCHITECTURAL TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 75)

if __name__ == '__main__':
    test_ai_native_architecture()
