"""
Vercel Serverless Function Handler for LendAssist API.
Exposes:
- POST /api/v1/chat
- GET  /api/v1/support/tickets
- POST /api/v1/support/tickets/action
- GET  /api/v1/system/events
- GET  /api/v1/analytics
"""

from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
import sys
import os

# Ensure backend modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.server import (
    process_chat_message,
    SUPPORT_TICKETS,
    SYSTEM_EVENTS,
    ANALYTICS_DATA,
    log_event
)

class handler(BaseHTTPRequestHandler):
    def _resolve_route(self) -> str:
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if "endpoint" in qs and qs["endpoint"]:
            return "/api/v1/" + qs["endpoint"][0].lstrip("/")
        
        candidates = [
            self.headers.get("x-forwarded-url"),
            self.headers.get("x-matched-path"),
            self.headers.get("x-vercel-matched-path"),
            parsed.path
        ]
        for c in candidates:
            if c and "/api/v1/" in c:
                return urllib.parse.urlparse(c).path
        return parsed.path

    def do_GET(self):
        route = self._resolve_route()
        
        if "/api/v1/support/tickets" in route:
            self.send_json_response(SUPPORT_TICKETS)
            return
        elif "/api/v1/system/events" in route:
            self.send_json_response(SYSTEM_EVENTS)
            return
        elif "/api/v1/analytics" in route:
            self.send_json_response(ANALYTICS_DATA)
            return
            
        self.send_json_response({
            "status": "LendAssist API operational",
            "resolved_route": route,
            "raw_path": self.path
        })

    def do_POST(self):
        route = self._resolve_route()
        content_length = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
        try:
            req_data = json.loads(post_body) if post_body else {}
        except Exception:
            req_data = {}

        if "/api/v1/chat" in route:
            result = process_chat_message(req_data)
            self.send_json_response(result)
            return
        elif "/api/v1/support/tickets/action" in route:
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
            
        self.send_json_response({"error": "Endpoint not found", "route": route}, status=404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

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
