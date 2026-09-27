import re
import random
from typing import Dict, Any, Tuple, Optional

class InteractiveJourneyEngine:
    """
    Stateful conversational multi-turn session engine.
    Maintains user state, collected data (product, employment, income, PAN, OTP, loan amount),
    and guides them interactively turn-by-turn through Home Loan & LAMF funnels.
    """

    # In-memory session store: session_id -> state dict
    SESSIONS: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_or_create_session(cls, session_id: str, context_app_id: Optional[str] = None) -> Dict[str, Any]:
        if session_id not in cls.SESSIONS:
            cls.SESSIONS[session_id] = {
                "session_id": session_id,
                "current_journey": None,  # "HOME_LOAN" or "LAMF"
                "current_step": "IDLE",   # IDLE, ASKING_EMPLOYMENT, ASKING_INCOME, ASKING_LOAN_AMOUNT, ASKING_PAN, ASKING_OTP, PLEDGE_SELECTION, AUTOPAY_SETUP, COMPLETED
                "user_data": {
                    "app_id": context_app_id,
                    "name": None,
                    "employment_type": None,  # salaried / self-employed
                    "monthly_income": None,
                    "loan_amount": None,
                    "pan": None,
                    "otp_sent": None,
                    "portfolio_val": None,
                    "sanction_limit": None,
                    "documents_uploaded": []
                },
                "history": []
            }
        return cls.SESSIONS[session_id]

    @classmethod
    def reset_session(cls, session_id: str):
        if session_id in cls.SESSIONS:
            del cls.SESSIONS[session_id]

    @classmethod
    def handle_turn(cls, session_id: str, message: str, context_app_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Evaluates message in the context of the active multi-turn journey state.
        Returns a response dict if state transition handled, or None to fall back to general intent router.
        """
        session = cls.get_or_create_session(session_id, context_app_id)
        step = session["current_step"]
        msg = message.strip()
        msg_lower = msg.lower()

        # Check for user resetting/starting fresh
        if any(k in msg_lower for k in ["start over", "reset", "start again", "restart"]):
            cls.reset_session(session_id)
            session = cls.get_or_create_session(session_id, context_app_id)
            return {
                "response": "No problem, let's start fresh! 😊\n\nWhich journey would you like me to assist you with?",
                "action_chips": ["🏠 Home Loan Application", "📈 Loan Against Mutual Funds (LAMF)", "🔍 Check Status"],
                "step": "IDLE",
                "journey": None
            }

        # Step 0: User expresses intent to start or apply
        if step == "IDLE":
            if any(k in msg_lower for k in ["apply for home loan", "home loan application", "want a home loan", "buy a house"]):
                session["current_journey"] = "HOME_LOAN"
                session["current_step"] = "ASKING_EMPLOYMENT"
                return {
                    "response": (
                        "Awesome! I'd love to help you apply for an **Easy Home Loan**! 🏠✨\n\n"
                        "To give you the exact document checklist and interest rate brackets, could you tell me your **employment type**?\n\n"
                        "Are you **Salaried** or **Self-Employed**?"
                    ),
                    "action_chips": ["👔 Salaried", "💼 Self-Employed"],
                    "step": "ASKING_EMPLOYMENT",
                    "journey": "HOME_LOAN"
                }

            if any(k in msg_lower for k in ["apply for lamf", "apply for loan against mutual", "loan against mutual funds", "pledge mutual funds", "groww loan", "yenmo loan"]):
                session["current_journey"] = "LAMF"
                session["current_step"] = "ASKING_PAN"
                return {
                    "response": (
                        "Fantastic choice! With **Loan Against Mutual Funds (LAMF)**, you can unlock up to 50% cash on Equity and 80% on Debt funds without selling a single unit. Your SIPs and returns continue uninterrupted! 🚀\n\n"
                        "To fetch your approved portfolio from CAMS and KFintech (with 0 impact on your CIBIL), please enter your **10-character PAN number** (e.g., `ABCDE1234F`)."
                    ),
                    "action_chips": ["Use Sample PAN (PAN12345)", "How does CAMS fetch work?", "Is CIBIL affected?"],
                    "step": "ASKING_PAN",
                    "journey": "LAMF"
                }

        # ==========================================================
        # MULTI-TURN FLOW: HOME LOAN
        # ==========================================================
        if session["current_journey"] == "HOME_LOAN":

            # Sub-step 1: Employment Type
            if step == "ASKING_EMPLOYMENT":
                if "salaried" in msg_lower:
                    session["user_data"]["employment_type"] = "Salaried"
                    session["current_step"] = "ASKING_INCOME"
                    return {
                        "response": (
                            "Got it — **Salaried professional**! 👍\n\n"
                            "Could you share your approximate **monthly net in-hand salary**? (e.g. ₹50,000, ₹1 Lakh, or 75000)"
                        ),
                        "action_chips": ["₹50,000 / month", "₹85,000 / month", "₹1.5 Lakh / month"],
                        "step": "ASKING_INCOME",
                        "journey": "HOME_LOAN"
                    }
                elif "self" in msg_lower or "business" in msg_lower or "freelance" in msg_lower:
                    session["user_data"]["employment_type"] = "Self-Employed"
                    session["current_step"] = "ASKING_INCOME"
                    return {
                        "response": (
                            "Understood — **Self-Employed / Business owner**! 💼\n\n"
                            "What is your approximate **annual taxable income** as per your latest ITR? (e.g. ₹8 Lakh, ₹15 Lakh)"
                        ),
                        "action_chips": ["₹6 Lakh / year", "₹12 Lakh / year", "₹25 Lakh / year"],
                        "step": "ASKING_INCOME",
                        "journey": "HOME_LOAN"
                    }
                else:
                    return {
                        "response": "Please choose whether you are **Salaried** (earning a fixed monthly pay) or **Self-Employed** (running a business/profession).",
                        "action_chips": ["👔 Salaried", "💼 Self-Employed"],
                        "step": "ASKING_EMPLOYMENT",
                        "journey": "HOME_LOAN"
                    }

            # Sub-step 2: Income
            if step == "ASKING_INCOME":
                session["user_data"]["monthly_income"] = msg
                session["current_step"] = "ASKING_LOAN_AMOUNT"
                emp = session["user_data"]["employment_type"]
                return {
                    "response": (
                        f"Noted: {msg} income for {emp} profile.\n\n"
                        f"How much **loan amount** are you looking for, and in which city is the property located? (e.g. ₹35 Lakh in Mumbai, or ₹50 Lakh in Bangalore)"
                    ),
                    "action_chips": ["₹25 Lakh in Mumbai", "₹40 Lakh in Pune", "₹60 Lakh in Bangalore"],
                    "step": "ASKING_LOAN_AMOUNT",
                    "journey": "HOME_LOAN"
                }

            # Sub-step 3: Loan Amount & City -> Generate Tailored Checklist & Offer PAN KYC
            if step == "ASKING_LOAN_AMOUNT":
                session["user_data"]["loan_amount"] = msg
                session["current_step"] = "ASKING_PAN"
                emp = session["user_data"]["employment_type"]
                
                checklist = (
                    "• **ID & Address Proof**: PAN card + Aadhaar\n"
                    "• **Income Proof**: Last 3 months payslips + 6 months salary account bank statement + latest Form 16\n"
                    "• **Property Documents**: Allotment letter / agreement to sale + chain deeds"
                ) if emp == "Salaried" else (
                    "• **ID & Address Proof**: PAN card + Aadhaar\n"
                    "• **Business Proof**: GST registration / MSME certificate\n"
                    "• **Income Proof**: Last 2-3 years ITR with CA-certified computation, P&L, balance sheet + 12 months current bank statements\n"
                    "• **Property Documents**: Copy of Title Deeds + Approved building plan"
                )

                return {
                    "response": (
                        f"Here is your personalized Home Loan roadmap for **{msg}**! 🎯\n\n"
                        f"📋 **Required Documents for your {emp} profile**:\n{checklist}\n\n"
                        f"Shall we pre-fill your application and check your eligible interest rate bracket? Please share your **PAN Number** to get started."
                    ),
                    "action_chips": ["Use Sample PAN (PAN12345)", "Calculate EMI for this amount", "Talk to Loan Officer"],
                    "step": "ASKING_PAN",
                    "journey": "HOME_LOAN"
                }

            # Sub-step 4: PAN KYC
            if step == "ASKING_PAN":
                pan_val = msg.upper().strip()
                session["user_data"]["pan"] = pan_val
                session["current_step"] = "ASKING_OTP"
                session["user_data"]["otp_sent"] = "4821"  # Simulated OTP

                return {
                    "response": (
                        f"PAN **{pan_val}** verified with NSDL database! ✅\n"
                        f"Name on PAN: **{session['user_data'].get('name') or 'Rahul Sharma'}**\n\n"
                        f"We just sent a 4-digit verification OTP to your registered mobile `XXXXXX5929`. Please enter the OTP to confirm your identity (Hint: enter `4821`)."
                    ),
                    "action_chips": ["Enter 4821", "Resend OTP", "Change Mobile Number"],
                    "step": "ASKING_OTP",
                    "journey": "HOME_LOAN"
                }

            # Sub-step 5: OTP Confirmation -> Application Created
            if step == "ASKING_OTP":
                if "4821" in msg or "verify" in msg_lower or "submit" in msg_lower:
                    new_app_id = "APP-HL-2026"
                    session["current_step"] = "COMPLETED"
                    session["user_data"]["app_id"] = new_app_id
                    return {
                        "response": (
                            f"🎉 **OTP Verified Successfully!**\n\n"
                            f"Your Home Loan Application **#{new_app_id}** has been created in our Loan Origination System (LOS)!\n\n"
                            f"• Customer: Rahul Sharma\n"
                            f"• Profile: {session['user_data']['employment_type']}\n"
                            f"• Indicative Rate: **8.65% to 8.85% p.a.**\n"
                            f"• Current Status: `DOCUMENTS_PENDING`\n\n"
                            f"You can now upload your salary slips and bank statement right here in the chat, or check your real-time status anytime!"
                        ),
                        "action_chips": ["Upload Salary Slips", "Check Application Status", "Calculate Amortization"],
                        "step": "COMPLETED",
                        "journey": "HOME_LOAN"
                    }
                else:
                    return {
                        "response": "The OTP you entered doesn't match our records. Please enter the 4-digit code sent to your mobile (or enter `4821` for this demo).",
                        "action_chips": ["Enter 4821", "Resend OTP"],
                        "step": "ASKING_OTP",
                        "journey": "HOME_LOAN"
                    }

        # ==========================================================
        # MULTI-TURN FLOW: LAMF (LOAN AGAINST MUTUAL FUNDS)
        # ==========================================================
        if session["current_journey"] == "LAMF":

            # Sub-step 1: PAN Fetch
            if step == "ASKING_PAN":
                pan_clean = re.sub(r'[^A-Za-z0-9]', '', msg).upper()
                session["user_data"]["pan"] = pan_clean
                session["user_data"]["portfolio_val"] = 640000
                session["user_data"]["sanction_limit"] = 320000
                session["current_step"] = "PLEDGE_SELECTION"

                return {
                    "response": (
                        f"Consolidated Account Statement (CAS) successfully fetched via CAMS & KFintech for PAN **{pan_clean}**! 📈🎉\n\n"
                        f"• Name: **Aryan Agarwal**\n"
                        f"• Total Approved Portfolio: **₹6,40,000**\n"
                        f"• Max Eligible Credit Line (50% LTV): **₹3,20,000**\n\n"
                        f"**Found 3 Eligible Funds**:\n"
                        f"1. *Quant Small Cap Fund* — Val: ₹3,00,000 (Limit: ₹1,50,000)\n"
                        f"2. *PGIM India Midcap Opportunities* — Val: ₹2,00,000 (Limit: ₹1,00,000)\n"
                        f"3. *ICICI Pru Nifty Next 50* — Val: ₹1,40,000 (Limit: ₹70,000)\n\n"
                        f"How much credit limit would you like to unlock today? (e.g. ₹1,60,000 or full ₹3,20,000)"
                    ),
                    "action_chips": ["Unlock ₹1,60,000", "Unlock Full ₹3,20,000", "Which funds are pledged?"],
                    "step": "PLEDGE_SELECTION",
                    "journey": "LAMF"
                }

            # Sub-step 2: Unit Selection -> RTA Lien OTP
            if step == "PLEDGE_SELECTION":
                amount_str = msg
                session["user_data"]["loan_amount"] = amount_str
                session["current_step"] = "ASKING_OTP"
                session["user_data"]["otp_sent"] = "9032"

                return {
                    "response": (
                        f"You have chosen to unlock **{amount_str}** against your selected funds. 🔒\n\n"
                        f"To authorize the lien marking with CAMS, an official 4-digit RTA OTP has been dispatched to your folio-registered mobile & email.\n\n"
                        f"Please enter the CAMS OTP to mark the lien (Hint: enter `9032`)."
                    ),
                    "action_chips": ["Enter 9032", "Resend CAMS OTP", "Why lien marking?"],
                    "step": "ASKING_OTP",
                    "journey": "LAMF"
                }

            # Sub-step 3: RTA OTP Verification -> AutoPay & KFS
            if step == "ASKING_OTP":
                if "9032" in msg or "verify" in msg_lower or "submit" in msg_lower:
                    session["current_step"] = "AUTOPAY_SETUP"
                    return {
                        "response": (
                            "✅ **CAMS Lien Marking Authorized!** Your mutual fund units remain 100% invested with uninterrupted returns.\n\n"
                            "**Next Step: Bank AutoPay (e-Mandate)**\n"
                            "• Linked Bank: **HDFC Bank (XXXX-3294)**\n"
                            "• Verification: Penny drop completed (₹1 credited to verify account)\n"
                            "• Monthly Rate: Flat 10.5% p.a. (pay only on what you withdraw!)\n"
                            "• Processing Fee: ₹1,179 (incl. GST)\n\n"
                            "Ready to authenticate AutoPay and sign the Key Fact Statement (KFS)?"
                        ),
                        "action_chips": ["Set Up AutoPay & e-Sign", "View Repayment Schedule", "What is APR?"],
                        "step": "AUTOPAY_SETUP",
                        "journey": "LAMF"
                    }
                else:
                    return {
                        "response": "Invalid CAMS OTP. Please enter the 4-digit authorization code (or enter `9032` for this demo).",
                        "action_chips": ["Enter 9032", "Resend CAMS OTP"],
                        "step": "ASKING_OTP",
                        "journey": "LAMF"
                    }

            # Sub-step 4: AutoPay Setup & e-Sign Completed
            if step == "AUTOPAY_SETUP":
                session["current_step"] = "COMPLETED"
                app_id = "APP-LAMF-8831"
                session["user_data"]["app_id"] = app_id
                return {
                    "response": (
                        f"🎊 **Congratulations! Your LAMF Credit Line is LIVE!** 💸\n\n"
                        f"• Account ID: **{app_id}**\n"
                        f"• Withdrawable Limit: **₹1,60,000**\n"
                        f"• Interest Rate: 10.5% p.a. (Simple reducing balance)\n"
                        f"• Foreclosure Charges: ₹0 (Nil)\n\n"
                        f"Funds will be disbursed into your HDFC Bank account within 2 hours. You can withdraw, prepay, or track your balance right here anytime!"
                    ),
                    "action_chips": ["Check Withdrawable Balance", "Calculate Interest on ₹50k", "Return to Home"],
                    "step": "COMPLETED",
                    "journey": "LAMF"
                }

        # Step not handled in state machine -> pass to intent classifier
        return None
