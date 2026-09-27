import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import http.server
import socketserver
import urllib.parse
import json
import time
from backend.app.cognitive_engine import DialogueManager
from backend.app.policy_engine import PolicyEngine
from backend.app.domain_guard import DomainGuardrail

PORT = 8080

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(APP_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
STATIC_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
KB_FILE = os.path.join(APP_DIR, "knowledge_base.json")

SUPPORT_TICKETS = []
SYSTEM_EVENTS = []

def log_event(event_type, details):
    event = {
        "event_id": f"EVT-{len(SYSTEM_EVENTS)+1:04d}",
        "timestamp": time.strftime("%H:%M:%S"),
        "type": event_type,
        "details": details
    }
    SYSTEM_EVENTS.insert(0, event)
    if len(SYSTEM_EVENTS) > 100:
        SYSTEM_EVENTS.pop()

from backend.app.escalation_engine import EscalationDecisionSystem

ANALYTICS_DATA = {
    "total_conversations": 1284,
    "ai_resolution_rate": 74.2,
    "self_service_resolution_rate": 74.2,
    "human_escalation_rate": 17.8,
    "escalation_rate": 17.8,
    "unresolved_rate": 8.0,
    "avg_turns": 4.1,
    "csat": 4.4,
    "escalation_precision": 89.2,
    "hallucination_rate": 0.4,
    "avg_handle_time_mins": 4.8,
    "baseline_handle_time_mins": 14.5,
    "first_contact_resolution": 82.5,
    "p95_latency_ms": 420,
    "strategy_a_metrics": { "name": "Ultra-Concise (1 sentence)", "turns": 3.2, "csat": 4.1, "escalations": 21.0, "p95_latency_ms": 380 },
    "strategy_b_metrics": { "name": "Natural Concise (1-3 sentences)", "turns": 4.1, "csat": 4.6, "escalations": 14.5, "p95_latency_ms": 420 }
}

def process_chat_message(req_data):
    start_time = time.time()
    msg = req_data.get("message", "").strip()
    msg_lower = msg.lower()
    session_id = req_data.get("conversation_id", "default_session")
    auth_state = req_data.get("auth_state", False)
    app_id = req_data.get("app_id")
    simulation = req_data.get("simulation", {})
    strategy = req_data.get("strategy", "natural_concise")

    log_event("CHAT_MESSAGE_RECEIVED", {
        "msg": msg, "auth": auth_state, "app_id": app_id, 
        "session": session_id, "simulation": simulation, "strategy": strategy
    })

    # Retrieve or initialize session state for escalation context
    state = DialogueManager.get_or_create_state(session_id)
    state_dict = state.to_dict()
    if app_id:
        if "entities" not in state_dict:
            state_dict["entities"] = {}
        state_dict["entities"]["application_id"] = app_id
        if "HL" in app_id:
            state_dict["entities"]["name"] = "Rahul Sharma"
            state_dict["entities"]["product_type"] = "Home Loan"
        elif "LAMF" in app_id:
            state_dict["entities"]["name"] = "Aryan Agarwal"
            state_dict["entities"]["product_type"] = "Loan Against Mutual Funds (LAMF)"

    # Pre-detect preliminary intent for escalation scoring
    preliminary_intent = "GENERAL_INQUIRY"
    if any(k in msg_lower for k in ["stole", "fraud", "unauthorized", "stolen", "police", "hacked"]):
        preliminary_intent = "FRAUD_ESCALATION"
    elif any(k in msg_lower for k in ["die", "death", "deceased", "nominee"]):
        preliminary_intent = "LOAN_SETTLEMENT_DECEASED"
    elif any(k in msg_lower for k in ["talk to human", "speak to agent", "connect to executive", "human agent", "support person"]):
        preliminary_intent = "TALK_TO_AGENT"

    # Evaluate via Risk-Aware Escalation Decision System
    decision, factors, handoff_packet = EscalationDecisionSystem.evaluate(
        message=msg,
        intent=preliminary_intent,
        confidence=0.95,
        context=state_dict,
        simulated_overrides=simulation
    )

    # 1. If System Decides to ESCALATE:
    if decision == "ESCALATE" and handoff_packet:
        ticket = handoff_packet.to_dict()
        SUPPORT_TICKETS.insert(0, ticket)
        if len(SUPPORT_TICKETS) > 50:
            SUPPORT_TICKETS.pop()
        log_event("HUMAN_ESCALATION_TRIGGERED", ticket)

        desk_name = handoff_packet.ai_recommendation["assigned_desk"]
        resp_text = (
            f"I want to make sure you get immediate, specialized support. "
            f"I have created Priority Ticket **#{ticket['ticket_id']}** and routed your case directly to our **{desk_name}**.\n\n"
            f"A specialist has received your verified file and will assist you immediately."
        )
        latency = round((time.time() - start_time) * 1000, 1)
        return {
            "basket": "BASKET_4_HUMAN_ESCALATION",
            "intent": ticket["conversation"]["detected_intent"],
            "confidence": 0.99,
            "risk_level": "CRITICAL" if handoff_packet.priority == "P1_CRITICAL" else "HIGH",
            "escalation_score": factors.total_score(),
            "source_authority": "Escalation Decision System (CRM)",
            "latency_ms": latency,
            "response": resp_text,
            "ticket": ticket,
            "escalation_analysis": {
                "decision": "ESCALATE",
                "score": factors.total_score(),
                "level": handoff_packet.escalation_level,
                "priority": handoff_packet.priority,
                "factors": factors.to_dict(),
                "why": handoff_packet.ai_recommendation["reason_for_escalation"]
            },
            "action_chips": ["View Agent Workspace", "Call Priority Support (1800-EASY-HL)", "Return to Assistant"]
        }

    # 2. Guardrail: Unauthorized Credit Approval / Rate Override
    if any(k in msg_lower for k in ["approve my loan", "sanction my loan immediately", "reduce interest rate to 5%", "guarantee approval", "lower rate to 4%"]):
        resp_text = (
            "As an automated advisor, I cannot approve loans or override sanctioned interest rates. "
            "Approval and pricing are determined by our credit underwriting team based on your documents, CIBIL score, and property evaluation."
        )
        latency = round((time.time() - start_time) * 1000, 1)
        return {
            "basket": "GUARDRAIL_DISCLOSURE",
            "intent": "RESTRICTED_LENDING_ACTION",
            "confidence": 0.99,
            "risk_level": "HIGH",
            "source_authority": "Credit Underwriting Policy",
            "latency_ms": latency,
            "response": resp_text,
            "escalation_analysis": {
                "decision": "ANSWER",
                "score": 0.25,
                "level": "LEVEL_0_AI",
                "priority": "P4_LOW",
                "factors": factors.to_dict(),
                "why": "Credit guardrail enforced: Autonomous rate modification blocked."
            },
            "action_chips": ["Check Eligibility Criteria", "Speak with Loan Officer"]
        }

    # 3. Domain Boundary Guardrail (Off-topic queries)
    is_domain, off_topic_msg = DomainGuardrail.check_query_domain(msg)
    if not is_domain:
        latency = round((time.time() - start_time) * 1000, 1)
        return {
            "basket": "OUT_OF_DOMAIN_REFRAME",
            "intent": "OUT_OF_DOMAIN_QUERY",
            "confidence": 0.99,
            "risk_level": "LOW",
            "source_authority": "Domain Boundary Guardrail",
            "latency_ms": latency,
            "response": off_topic_msg,
            "escalation_analysis": {
                "decision": "ANSWER",
                "score": 0.05,
                "level": "LEVEL_0_AI",
                "priority": "P4_LOW",
                "factors": factors.to_dict(),
                "why": "Polite out-of-domain reframing executed."
            },
            "action_chips": ["Apply for LAMF", "Home Loan Application", "Check Application Status", "Calculate EMI"]
        }

    # 4. Core Cognitive Dialogue Manager Execution
    result = DialogueManager.handle_message(session_id, msg)
    latency = round((time.time() - start_time) * 1000, 1)
    result["latency_ms"] = latency
    result["escalation_analysis"] = {
        "decision": decision,
        "score": factors.total_score(),
        "level": "LEVEL_0_AI" if factors.total_score() < 0.3 else "LEVEL_1_MONITORED",
        "priority": "P4_LOW",
        "factors": factors.to_dict(),
        "why": "Query handled safely by AI self-service within approved boundaries."
    }
    return result


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == "/" or path == "":
            self.path = "/index.html"
            return super().do_GET()
            
        if path == "/api/v1/support/tickets":
            self.send_json_response(SUPPORT_TICKETS)
            return
        elif path == "/api/v1/system/events":
            self.send_json_response(SYSTEM_EVENTS)
            return
        elif path == "/api/v1/analytics":
            self.send_json_response(ANALYTICS_DATA)
            return
            
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_length).decode('utf-8')
        try:
            req_data = json.loads(post_body) if post_body else {}
        except Exception:
            req_data = {}

        if parsed.path == "/api/v1/chat":
            result = process_chat_message(req_data)
            self.send_json_response(result)
            return
        elif parsed.path == "/api/v1/support/tickets/action":
            ticket_id = req_data.get("ticket_id")
            action = req_data.get("action", "TAKE")
            for t in SUPPORT_TICKETS:
                if t.get("ticket_id") == ticket_id:
                    t["status"] = "IN_PROGRESS" if action == "TAKE" else "RESOLVED"
                    log_event("TICKET_STATUS_UPDATED", {"ticket_id": ticket_id, "status": t["status"]})
                    self.send_json_response({"success": True, "ticket": t})
                    return
            self.send_json_response({"error": "Ticket not found"}, status=404)
            return
            
        self.send_json_response({"error": "Not found"}, status=404)

    def send_json_response(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
        print(f"Server started at http://localhost:{PORT}")
        httpd.serve_forever()
