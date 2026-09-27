import re
import math
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import os

app = FastAPI(title="Easy Home Finance & LAMF AI Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Knowledge Base
KB_FILE = os.path.join(os.path.dirname(__file__), "knowledge_base.json")
with open(KB_FILE, "r") as f:
    KNOWLEDGE_BASE = json.load(f)

# In-memory mock database
MOCK_APPLICATIONS = {
    "APP-HL-1092": {
        "app_id": "APP-HL-1092",
        "customer_name": "Rahul Sharma",
        "product": "HOME_LOAN",
        "loan_amount": 3500000,
        "status": "TECHNICAL_VERIFICATION_IN_PROGRESS",
        "stage": "Property Evaluation",
        "pending_documents": ["Property Chain Deeds", "Latest 3-Month Electricity Bill"],
        "tat_estimate": "3 business days",
        "sanction_issued": False
    },
    "APP-LAMF-8831": {
        "app_id": "APP-LAMF-8831",
        "customer_name": "Aryan Agarwal",
        "product": "LAMF",
        "portfolio_value": 640000,
        "sanction_limit": 320000,
        "status": "PLEDGE_CONFIRMATION_PENDING",
        "stage": "CAMS RTA Lien OTP",
        "pending_documents": [],
        "tat_estimate": "2 hours post OTP verification",
        "sanction_issued": True
    }
}

MOCK_PORTFOLIOS = {
    "PAN12345": {
        "customer_name": "Aryan Agarwal",
        "pan": "PAN12345",
        "total_portfolio": 640000,
        "schemes": [
            {"isin": "INF209K01157", "name": "Quant Small Cap Fund", "units": 1250.4, "nav": 240.5, "val": 300000, "ltv": 0.50, "limit": 150000, "eligible": True},
            {"isin": "INF109K01234", "name": "PGIM India Midcap Opportunities", "units": 1800.0, "nav": 111.1, "val": 200000, "ltv": 0.50, "limit": 100000, "eligible": True},
            {"isin": "INF090I01234", "name": "ICICI Prudential Nifty Next 50", "units": 2000.0, "nav": 70.0, "val": 140000, "ltv": 0.50, "limit": 70000, "eligible": True}
        ]
    }
}

SUPPORT_TICKETS = []
SYSTEM_EVENTS = []

def log_event(event_type: str, details: Dict[str, Any]):
    event = {
        "event_id": f"EVT-{len(SYSTEM_EVENTS)+1:04d}",
        "type": event_type,
        "details": details
    }
    SYSTEM_EVENTS.insert(0, event)
    if len(SYSTEM_EVENTS) > 100:
        SYSTEM_EVENTS.pop()

# Pydantic Request Models
class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "conv_default"
    auth_state: bool = False
    app_id: Optional[str] = None
    step_context: Optional[str] = None

class EMIRequest(BaseModel):
    principal: float
    annual_rate: float
    tenure_months: int

class SupportTicketRequest(BaseModel):
    customer_id: str
    app_id: Optional[str] = None
    intent: str
    reason: str
    conversation_summary: str
    troubleshooting_done: List[str]

# Deterministic Calculator Engine
def calculate_emi_details(principal: float, annual_rate: float, tenure_months: int) -> Dict[str, Any]:
    r = (annual_rate / 12) / 100
    if r == 0:
        emi = principal / tenure_months
    else:
        emi = (principal * r * math.pow(1 + r, tenure_months)) / (math.pow(1 + r, tenure_months) - 1)
    
    total_repayment = emi * tenure_months
    total_interest = total_repayment - principal
    
    # Monthly interest only (for LAMF overdraft line)
    monthly_od_interest = (principal * (annual_rate / 100)) / 12
    
    return {
        "principal": round(principal, 2),
        "annual_rate": annual_rate,
        "tenure_months": tenure_months,
        "monthly_emi": round(emi, 2),
        "total_interest": round(total_interest, 2),
        "total_repayment": round(total_repayment, 2),
        "monthly_od_interest_only": round(monthly_od_interest, 2)
    }

# RAG Search Function
def search_knowledge_base(query: str) -> Optional[Dict[str, Any]]:
    q_words = set(re.findall(r'\w+', query.lower()))
    best_chunk = None
    max_score = 0
    
    for chunk in KNOWLEDGE_BASE:
        score = 0
        keywords = set(chunk.get("keywords", []))
        for kw in keywords:
            for word in kw.split():
                if word in q_words:
                    score += 3
        # Match title/content
        content_words = set(re.findall(r'\w+', (chunk["title"] + " " + chunk["content"]).lower()))
        score += len(q_words.intersection(content_words))
        
        if score > max_score:
            max_score = score
            best_chunk = chunk
            
    return best_chunk if max_score >= 3 else None

# Orchestrator & Intent Router
@app.post("/api/v1/chat")
def process_chat(req: ChatRequest):
    msg = req.message.strip().lower()
    log_event("CHAT_MESSAGE_RECEIVED", {"msg": req.message, "auth": req.auth_state, "app_id": req.app_id})
    
    # LAYER 1: Safety & Regulatory Guardrails
    if any(phrase in msg for phrase in ["approve my loan", "sanction my loan immediately", "reduce interest rate to 5%", "guarantee approval"]):
        return {
            "basket": "GUARDRAIL_DISCLOSURE",
            "intent": "RESTRICTED_LENDING_ACTION",
            "confidence": 0.99,
            "response": "Easy Home Finance AI Assistant cannot approve, sanction, or alter credit decisions or interest rates. Final sanction is determined strictly by our underwriting team following regulatory and credit policy evaluations.",
            "action_chips": ["Check Eligibility Criteria", "Speak with Loan Officer"]
        }
        
    if any(phrase in msg for phrase in ["fraud", "police", "legal notice", "threat", "bribe", "hacked"]):
        ticket = {
            "ticket_id": f"TICK-{len(SUPPORT_TICKETS)+101}",
            "customer_id": "CUST-ESCALATED",
            "app_id": req.app_id or "UNKNOWN",
            "intent": "COMPLAINT_OR_FRAUD",
            "reason": "Immediate regulatory grievance / security trigger.",
            "conversation_summary": f"Customer flagged safety/legal issue: '{req.message}'",
            "troubleshooting_done": ["Immediate escalation initiated"]
        }
        SUPPORT_TICKETS.insert(0, ticket)
        log_event("HUMAN_ESCALATION_TRIGGERED", ticket)
        return {
            "basket": "BASKET_4_HUMAN_ESCALATION",
            "intent": "COMPLAINT_OR_FRAUD",
            "confidence": 1.0,
            "response": f"Your query has been escalated to our Senior Grievance & Risk Desk with high priority (Ticket #{ticket['ticket_id']}). An officer will reach out within 15 minutes.",
            "ticket": ticket,
            "action_chips": ["Call Priority Support (1800-EASY-HL)", "Return to Dashboard"]
        }

    # LAYER 2: Explicit Human Request
    if any(phrase in msg for phrase in ["talk to human", "speak to agent", "connect to executive", "human agent", "support person"]):
        ticket = {
            "ticket_id": f"TICK-{len(SUPPORT_TICKETS)+101}",
            "customer_id": "CUST-REQ",
            "app_id": req.app_id or "APP-CURRENT",
            "intent": "HUMAN_AGENT_REQUEST",
            "reason": "Customer requested human support directly.",
            "conversation_summary": req.message,
            "troubleshooting_done": ["Transferred on customer request"]
        }
        SUPPORT_TICKETS.insert(0, ticket)
        log_event("HUMAN_ESCALATION_TRIGGERED", ticket)
        return {
            "basket": "BASKET_4_HUMAN_ESCALATION",
            "intent": "HUMAN_AGENT_REQUEST",
            "confidence": 0.98,
            "response": f"I've initiated an agent transfer for you! Support Ticket #{ticket['ticket_id']} has been created. I am transferring our conversation transcript and application details to the agent now.",
            "ticket": ticket,
            "action_chips": ["View Ticket Status", "Resume Self-Service"]
        }

    # LAYER 3: Transactional Backend APIs (Basket 3)
    # 3.1 Status check
    if any(k in msg for k in ["status", "application status", "where is my loan", "track application"]):
        target_app = req.app_id or "APP-HL-1092"
        app_data = MOCK_APPLICATIONS.get(target_app)
        if not req.auth_state and not req.app_id:
            return {
                "basket": "BASKET_3_BACKEND_API",
                "intent": "APPLICATION_STATUS_AUTH_REQUIRED",
                "confidence": 0.95,
                "response": "To fetch your live application status securely, please authenticate with your registered mobile OTP or provide your Application ID (e.g. APP-HL-1092 or APP-LAMF-8831).",
                "action_chips": ["Use Sample APP-HL-1092", "Use Sample APP-LAMF-8831", "Log in via OTP"]
            }
        if app_data:
            pending_str = ", ".join(app_data["pending_documents"]) if app_data["pending_documents"] else "None (All documents verified)"
            resp_text = (
                f"**Application Status for {app_data['app_id']} ({app_data['customer_name']})**:\n"
                f"• Current Stage: **{app_data['stage']}**\n"
                f"• Status: `{app_data['status']}`\n"
                f"• Pending Items: {pending_str}\n"
                f"• Estimated TAT: {app_data['tat_estimate']}"
            )
            return {
                "basket": "BASKET_3_BACKEND_API",
                "intent": "APPLICATION_STATUS",
                "confidence": 0.96,
                "response": resp_text,
                "data": app_data,
                "action_chips": ["Upload Pending Documents", "Check Loan Details", "Help with Verification"]
            }
            
    # 3.2 Pending Documents
    if any(k in msg for k in ["pending document", "what documents are pending", "missing document"]):
        target_app = req.app_id or "APP-HL-1092"
        app_data = MOCK_APPLICATIONS.get(target_app)
        if app_data and app_data["pending_documents"]:
            docs = "\n".join([f"  {idx+1}. {d}" for idx, d in enumerate(app_data["pending_documents"])])
            return {
                "basket": "BASKET_3_BACKEND_API",
                "intent": "PENDING_DOCUMENTS",
                "confidence": 0.94,
                "response": f"According to our records for application **{app_data['app_id']}**, the following {len(app_data['pending_documents'])} document(s) are pending upload:\n\n{docs}\n\nYou can upload them directly in the app documents tab.",
                "action_chips": ["Upload Documents Now", "Document Guidelines", "Talk to Agent"]
            }

    # 3.3 EMI & Repayment Calculation
    emi_match = re.search(r'(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lac|l)?', msg)
    if "emi" in msg or "calculate" in msg or "how much emi" in msg:
        calc = calculate_emi_details(principal=2500000, annual_rate=8.75, tenure_months=240)
        lamf_calc = calculate_emi_details(principal=100000, annual_rate=10.5, tenure_months=12)
        return {
            "basket": "BASKET_3_BACKEND_API",
            "intent": "EMI_CALCULATION",
            "confidence": 0.95,
            "response": (
                f"Here are exact deterministic calculations:\n\n"
                f"🏠 **Home Loan Example (₹25 Lakh @ 8.75% for 20 Yrs)**:\n"
                f"• Monthly EMI: **₹{calc['monthly_emi']:,}**\n"
                f"• Total Repayment: ₹{calc['total_repayment']:,} (Principal ₹25L + Interest ₹{calc['total_interest']:,})\n\n"
                f"📈 **LAMF Overdraft Example (₹1,00,000 @ 10.5%)**:\n"
                f"• Monthly Interest Only: **₹{lamf_calc['monthly_od_interest_only']:,}/mo** (pay only when drawn)"
            ),
            "data": {"home_loan": calc, "lamf": lamf_calc},
            "action_chips": ["Custom EMI Calculator", "Apply for Home Loan", "Explore LAMF Limit"]
        }

    # LAYER 4: Guided Assistance & Journey Workflows (Basket 2)
    if any(k in msg for k in ["help me apply", "start application", "how to apply", "guided assistance", "step by step"]):
        return {
            "basket": "BASKET_2_GUIDED_WORKFLOW",
            "intent": "START_ASSISTED_JOURNEY",
            "confidence": 0.92,
            "response": "I can guide you step-by-step through our digital loan journeys! Which product would you like to explore today?",
            "step": "PRODUCT_SELECTION",
            "action_chips": ["🏠 Home Loan Application", "📈 Loan Against Mutual Funds (LAMF)", "🔍 Check Eligibility First"]
        }
        
    if "lamf" in msg or "mutual fund loan" in msg or "loan against mutual" in msg or req.step_context == "LAMF_JOURNEY":
        return {
            "basket": "BASKET_2_GUIDED_WORKFLOW",
            "intent": "LAMF_GUIDED_STEPS",
            "confidence": 0.93,
            "response": (
                "**Loan Against Mutual Funds (LAMF) — 4 Instant Steps**:\n\n"
                "1️⃣ **Fetch Portfolio**: We pull your CAMS/KFintech holdings using your PAN (0 impact on CIBIL).\n"
                "2️⃣ **Choose Units to Pledge**: Get 50% LTV on Equity or up to 80% on Debt funds.\n"
                "3️⃣ **Verify via RTA OTP**: Authorize lien via official CAMS/KFintech OTP.\n"
                "4️⃣ **AutoPay & Instant Cash**: Set up e-Mandate and draw funds into your bank account.\n\n"
                "Ready to see your eligible loan limit?"
            ),
            "action_chips": ["Fetch My MF Limit (PAN12345)", "What happens if Nifty crashes?", "Is my SIP stopped?"]
        }

    # LAYER 5: RAG / Knowledge Base (Basket 1)
    rag_hit = search_knowledge_base(req.message)
    if rag_hit:
        return {
            "basket": "BASKET_1_FAQ_RAG",
            "intent": rag_hit["category"],
            "chunk_id": rag_hit["chunk_id"],
            "confidence": 0.88,
            "response": rag_hit["content"],
            "reference_title": rag_hit["title"],
            "action_chips": ["Check Application Status", "Calculate EMI", "Start Application"]
        }

    # Fallback with clarifying question
    return {
        "basket": "BASKET_1_FAQ_RAG",
        "intent": "GENERAL_CLARIFICATION",
        "confidence": 0.65,
        "response": "I'm here to help with your Home Loan or Loan Against Mutual Funds journey! You can check your application status, calculate your exact EMI, understand required documents, or begin an instant application.",
        "action_chips": ["Application Status", "Documents Required", "LAMF Details", "Talk to an Agent"]
    }

# Core Service APIs
@app.get("/api/v1/loan/status")
def get_loan_status(app_id: str):
    log_event("API_CALL_GET_STATUS", {"app_id": app_id})
    if app_id in MOCK_APPLICATIONS:
        return MOCK_APPLICATIONS[app_id]
    raise HTTPException(status_code=404, detail="Application ID not found in LOS")

@app.get("/api/v1/portfolio/credit-limit")
def get_portfolio_limit(pan: str):
    log_event("API_CALL_PORTFOLIO_FETCH", {"pan": pan})
    data = MOCK_PORTFOLIOS.get(pan.upper())
    if not data:
        return {
            "pan": pan,
            "customer_name": "Applicant",
            "total_portfolio": 35000,
            "eligible": False,
            "message": "Approved mutual fund portfolio is below minimum threshold of ₹50,000.",
            "schemes": []
        }
    total_limit = sum(s["limit"] for s in data["schemes"])
    return {
        "pan": pan,
        "customer_name": data["customer_name"],
        "total_portfolio": data["total_portfolio"],
        "eligible": True,
        "max_sanction_limit": total_limit,
        "schemes": data["schemes"]
    }

@app.post("/api/v1/calculator/emi")
def api_calc_emi(req: EMIRequest):
    return calculate_emi_details(req.principal, req.annual_rate, req.tenure_months)

@app.get("/api/v1/support/tickets")
def list_tickets():
    return SUPPORT_TICKETS

@app.get("/api/v1/system/events")
def list_events():
    return SYSTEM_EVENTS

# Mount Static UI
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "public")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
