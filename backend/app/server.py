import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import http.server
import socketserver
import urllib.parse
import json
import time
import re
from typing import Dict, Any, Optional, List
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

class EventNormalizer:
    @classmethod
    def normalize(cls, req_data: Dict[str, Any]) -> Dict[str, Any]:
        raw_msg = req_data.get("message", "").strip()
        msg_lower = raw_msg.lower()
        if any(k in msg_lower for k in ["call priority support", "1800-easy-hl"]):
            return {"type": "UI_ACTION", "action": "CALL_PRIORITY_SUPPORT", "payload": req_data}
        elif "return to assistant" in msg_lower:
            return {"type": "UI_ACTION", "action": "RETURN_TO_ASSISTANT", "payload": req_data}
        elif "view agent workspace" in msg_lower:
            return {"type": "UI_ACTION", "action": "VIEW_AGENT_WORKSPACE", "payload": req_data}
        return {"type": "CUSTOMER_MESSAGE", "message": raw_msg, "payload": req_data}


class ActionHandler:
    @classmethod
    def handle_ui_action(cls, action: str, state: Any, req_data: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        latency = round((time.time() - start_time) * 1000, 1)
        app_id = state.entities.get("application_id") or state.entities.get("app_id") or "APP-HL-1092"
        if action == "CALL_PRIORITY_SUPPORT":
            log_event("UI_ACTION_CALL_SUPPORT", {"app_id": app_id})
            return {
                "basket": "BASKET_4_HUMAN_ESCALATION",
                "intent": "CALL_PRIORITY_SUPPORT",
                "confidence": 0.99,
                "risk_level": "HIGH",
                "source_authority": "Priority Support Gateway",
                "latency_ms": latency,
                "response": "Connecting you directly to our Priority Care Desk at **1800-EASY-HL (1800-3279-45)**. Your verified loan file is flagged for immediate executive assistance.",
                "action_chips": ["View Agent Workspace", "Return to Assistant"],
                "escalation_analysis": {
                    "decision": "ESCALATE",
                    "score": 0.85,
                    "level": "LEVEL_3_PRIORITY",
                    "priority": "P1_CRITICAL",
                    "factors": {"risk_score": 0.0, "explicit_request": 0.85, "repeated_failure": 0.0, "ai_uncertainty": 0.0, "customer_frustration": 0.0, "workflow_failure": 0.0},
                    "why": "Customer initiated direct phone connection to Priority Support."
                }
            }
        elif action == "RETURN_TO_ASSISTANT":
            state.conversation_state = "NORMAL"
            log_event("UI_ACTION_RETURN_ASSISTANT", {"app_id": app_id})
            return {
                "basket": "BASKET_2_GUIDED_WORKFLOW",
                "intent": "RETURN_TO_ASSISTANT",
                "confidence": 0.99,
                "risk_level": "LOW",
                "source_authority": "Cognitive Dialogue Manager",
                "latency_ms": latency,
                "response": f"Welcome back! Your application for **{app_id}** is safely preserved. What would you like to explore next?",
                "action_chips": ["Check Application Status", "Explain Agreement / KFS", "Apply for LAMF"],
                "escalation_analysis": {
                    "decision": "ANSWER",
                    "score": 0.0,
                    "level": "LEVEL_0_AI",
                    "priority": "P4_LOW",
                    "factors": {"risk_score": 0.0, "explicit_request": 0.0, "repeated_failure": 0.0, "ai_uncertainty": 0.0, "customer_frustration": 0.0, "workflow_failure": 0.0},
                    "why": "Customer returned to digital assistant from human workspace."
                }
            }
        elif action == "VIEW_AGENT_WORKSPACE":
            return {
                "basket": "BASKET_4_HUMAN_ESCALATION",
                "intent": "VIEW_AGENT_WORKSPACE",
                "confidence": 0.99,
                "risk_level": "LOW",
                "source_authority": "Agent Workspace View",
                "latency_ms": latency,
                "response": "Opening Agent Workspace Dossier...",
                "action_chips": ["Return to Assistant"],
                "escalation_analysis": {
                    "decision": "ESCALATE",
                    "score": 0.70,
                    "level": "LEVEL_3_PRIORITY",
                    "priority": "P2_HIGH",
                    "factors": {"risk_score": 0.0, "explicit_request": 0.85, "repeated_failure": 0.0, "ai_uncertainty": 0.0, "customer_frustration": 0.0, "workflow_failure": 0.0},
                    "why": "Agent Workspace Dossier accessed."
                }
            }
        return {
            "basket": "BASKET_2_GUIDED_WORKFLOW",
            "intent": "GENERAL_CONVERSATION",
            "confidence": 0.99,
            "risk_level": "LOW",
            "source_authority": "System Event Handler",
            "latency_ms": latency,
            "response": "Ready to assist you with your loan options.",
            "action_chips": ["Apply for LAMF", "Check Application Status"]
        }


def process_chat_message(req_data):
    start_time = time.time()
    session_id = req_data.get("conversation_id", "default_session")
    auth_state = req_data.get("auth_state", False)
    app_id = req_data.get("app_id")
    simulation = req_data.get("simulation", {})
    strategy = req_data.get("strategy", "natural_concise")

    # 1. Retrieve & actively sync session context
    state = DialogueManager.get_or_create_state(session_id)
    if app_id:
        state.set_context(app_id)
    state_dict = state.to_dict()

    # 2. Event Normalization (Separate UI_ACTION from CUSTOMER_MESSAGE)
    event = EventNormalizer.normalize(req_data)
    if event["type"] == "UI_ACTION":
        return ActionHandler.handle_ui_action(event["action"], state, req_data, start_time)

    msg = req_data.get("message", "").strip()
    msg_lower = msg.lower()

    log_event("CHAT_MESSAGE_RECEIVED", {
        "msg": msg, "auth": auth_state, "app_id": app_id, 
        "session": session_id, "simulation": simulation, "strategy": strategy
    })

    # 0. Security, Prompt Injection & Compliance Guardrail
    security_check = DomainGuardrail.inspect_security_and_compliance(msg)
    if security_check:
        latency = round((time.time() - start_time) * 1000, 1)
        security_check["latency_ms"] = latency
        return security_check

    # 3. PRIORITY ROUTER: Hierarchy of System Intents
    preliminary_intent = "GENERAL_INQUIRY"

    # Priority 1: Emergency & Fraud
    if any(k in msg_lower for k in [
        "stole", "fraud", "unauthorized", "stolen", "police", "hacked",
        "someone took a loan using my account", "someone took a loan", "unauthorized debit", "compromised"
    ]):
        preliminary_intent = "FRAUD_ESCALATION"

    # Priority 2: Human Agent Request (Explicit, Indirect & Hinglish)
    elif (
        any(re.search(pat, msg_lower) for pat in [
            r'\b(?:connect|talk|speak)\s+(?:me\s+)?(?:to\s+|with\s+)?(?:an?\s+)?(?:agent|human|person|executive|representative|specialist|someone|somebody|customer\s+care|customer\s+support|your\s+team)\b',
            r'\b(?:i\s+want\s+(?:a\s+)?human|i\s+want\s+(?:an?\s+)?actual\s+person|i\s+want\s+customer\s+support|let\s+me\s+speak|call\s+support|human\s+agent|real\s+person|customer\s+care|support\s+person)\b',
            r'\b(?:don\'t|dont)\s+want\s+to\s+deal\s+with\s+a\s+bot\b',
            r'\b(?:can|could)\s+someone\s+help\s+me\s+with\s+this\b',
            r'\b(?:is\s+there\s+a\s+real\s+person|put\s+me\s+through\s+to\s+support|need\s+to\s+speak\s+with\s+somebody)\b',
            r'\b(?:get\s+an\s+executive\s+on\s+this|rather\s+talk\s+to\s+a\s+human|let\s+me\s+talk\s+to\s+your\s+team)\b',
            r'\b(?:someone\s+from\s+support\s+call\s+me|connect\s+me\s+to\s+someone|agent\s+se\s+baat\s+kara\s+do)\b'
        ]) or
        any(k in msg_lower for k in [
            "connect with an agent", "connect with agent", "connect me with an agent",
            "talk to a human", "talk to human", "talk to someone", "i want a human",
            "i want customer support", "let me speak to a representative", "call support",
            "connect with customer care", "speak to agent", "connect to executive",
            "speak to a real person", "human agent", "customer care agent",
            "agent se baat kara do", "put me through to support", "i want an actual person",
            "enough, connect me to someone"
        ]) or msg_lower == "agent"
    ) and not re.search(r'\bcan\s+you\s+help\s+me\b', msg_lower):
        preliminary_intent = "HUMAN_HANDOFF"

    # Priority 3: Workflow Failures (Bank Verification / Penny Drop / KYC / RTA)
    elif (
        any(k in msg_lower for k in [
            "penny drop verification failed", "penny drop failed", "my penny drop failed",
            "bank verification isn't working", "bank verification is not working",
            "account verification failed", "the bank check failed", "my ifsc verification didn't work",
            "account validation failed", "verification isn't going through",
            "my bank thing didn't work", "the verification just keeps failing", "why isn't my account getting verified",
            "bank check failed again", "penny drop isn't happening", "it said verification unsuccessful",
            "my account verification got rejected", "the ₹1 verification didn't go through",
            "the 1 rupee verification didn't go through", "that small amount verification failed",
            "bank validation is stuck", "it's not accepting my bank details",
            "everything is correct but it still says failed", "penny drop fail", "penny drp failed",
            "my bank verfication faild", "bank accnt not verifing", "why pennydrop not working",
            "verification nahi ho raha", "bank verify nhi hua", "mera bank verify nahi ho rha",
            "penny drop baar baar fail ho raha", "penny drop fail ho gaya", "bhai bank verification nahi ho rha",
            "account number sahi hai fir bhi verify nahi hua", "ifsc correct hai but verification failed",
            "baar baar fail ho raha hai"
        ]) or (
            msg_lower in ["it failed", "failed", "it failed again", "verification failed"] and
            (state.active_goal == "BANK_ACCOUNT_CHANGE" or state.workflow_state in ["BANK_VERIFICATION", "AUTOPAY_REVIEW"] or state.failed_attempts > 0)
        )
    ):
        preliminary_intent = "BANK_VERIFICATION_FAILURE"

    elif any(k in msg_lower for k in ["die", "death", "deceased", "nominee"]):
        preliminary_intent = "LOAN_SETTLEMENT_DECEASED"

    # Priority 3B: Mixed Intent (e.g. Penny drop failed + What's my rate?)
    elif ("penny drop" in msg_lower or "bank" in msg_lower) and any(k in msg_lower for k in ["interest rate", "how much i can borrow", "foreclosure"]):
        preliminary_intent = "MIXED_QUERY_AND_ACTION"

    elif any(k in msg_lower for k in [
        "try the verification again", "try verification again", "retry verification",
        "retry penny drop", "retry again", "try the bank check again",
        "again", "try that again", "do it once more", "retry",
        "isko dobara try kar sakte hain kya?", "isko dobara try kar sakte hain kya"
    ]) and (state.failed_attempts > 0 or state.workflow_state in ["BANK_VERIFICATION", "AUTOPAY_REVIEW"] or state.active_goal == "BANK_ACCOUNT_CHANGE"):
        preliminary_intent = "WORKFLOW_CONTINUATION"

    # Priority 3C: Repeated Frustration Accumulation
    elif any(k in msg_lower for k in ["nothing is working", "why the hell does this keep failing", "tried this three times", "third time"]) and (state.failed_attempts >= 1 or state.conversation_state == "ESCALATING"):
        preliminary_intent = "HUMAN_HANDOFF"

    # 4. Evaluate via Risk-Aware Escalation Decision System
    decision, factors, handoff_packet = EscalationDecisionSystem.evaluate(
        message=msg,
        intent=preliminary_intent,
        confidence=0.95,
        context=state_dict,
        simulated_overrides=simulation
    )

    # 5. If System Decides to ESCALATE:
    if decision == "ESCALATE" and handoff_packet:
        state.failed_attempts += 1
        state.conversation_state = "ESCALATING"
        ticket = handoff_packet.to_dict()
        SUPPORT_TICKETS.insert(0, ticket)
        if len(SUPPORT_TICKETS) > 50:
            SUPPORT_TICKETS.pop()
        log_event("HUMAN_ESCALATION_TRIGGERED", ticket)

        desk_name = handoff_packet.ai_recommendation["assigned_desk"]
        if preliminary_intent in ["HUMAN_HANDOFF", "TALK_TO_AGENT"]:
            resp_text = (
                "Absolutely. I’ll connect you with a support specialist and share this conversation with them so you don’t have to repeat yourself."
            )
            ticket["conversation"]["detected_intent"] = "HUMAN_HANDOFF"
        elif preliminary_intent == "BANK_VERIFICATION_FAILURE":
            resp_text = (
                f"The bank verification has failed again. Rather than making you retry repeatedly, "
                f"I have created Priority Ticket **#{ticket['ticket_id']}** and routed your case directly to our **{desk_name}** team to unblock your account."
            )
        else:
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

    # 6. Guardrail: Unauthorized Credit Approval / Rate Override
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

    # 7. Core Cognitive Dialogue Manager Execution
    result = DialogueManager.handle_message(session_id, msg)

    # 8. Domain Boundary Guardrail (Off-topic queries - checked as last resort)
    if result.get("intent") == "CLARIFICATION_REQUIRED":
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
