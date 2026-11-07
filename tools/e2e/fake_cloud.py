"""
Ghostline E2E Fake Cloud Provider Mock Server.
Reproduces real Cloudflare anti-bot blocks, Groq error shapes,
xAI error shapes, retired model 404s, and 429 rate limits with Retry-After.
"""

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger("fake_cloud")


class FakeCloudRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default stderr spam
        pass

    def do_GET(self):
        self._handle_request()

    def do_POST(self):
        self._handle_request()

    def _handle_request(self):
        user_agent = self.headers.get("User-Agent", "")
        auth_header = self.headers.get("Authorization", "")
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Cloudflare Anti-Bot Simulation:
        # Default python-requests / Python-urllib agents are blocked with 403 error code 1010
        if "cloudflare" in self.path or "api.groq.com" in self.headers.get("Host", ""):
            is_python_default = "python-requests" in user_agent.lower() or "python-urllib" in user_agent.lower()
            if is_python_default:
                self.send_response(403)
                self.send_header("Content-Type", "text/html; charset=UTF-8")
                self.send_header("CF-Ray", "8f1234567890abcd-IAD")
                self.end_headers()
                html = (
                    "<!DOCTYPE html><html><head><title>Access Denied | Cloudflare</title></head>"
                    "<body><h1>403 Forbidden</h1><p>error code: 1010</p>"
                    "<p>The owner of this website has banned your access based on your client's browser's signature.</p>"
                    "</body></html>"
                )
                self.wfile.write(html.encode("utf-8"))
                return

        if path == "/cloudflare-test":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK: Cloudflare test passed with valid User-Agent")
            return

        # Read POST body if present
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        body_json: Dict[str, Any] = {}
        if body:
            try:
                body_json = json.loads(body.decode("utf-8"))
            except Exception:
                pass

        model_requested = body_json.get("model", "")

        # 2. Key or Model-driven error scenarios:
        # Scenario: 401 Rejected API Key
        if "invalid-key" in auth_header or "test-401" in auth_header:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("x-request-id", "req_401_invalid_key")
            self.end_headers()
            err = {
                "error": {
                    "message": "Invalid API Key provided",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key"
                }
            }
            self.wfile.write(json.dumps(err).encode("utf-8"))
            return

        # Scenario: Groq 403 Not Eligible / Organization Restricted
        if "groq-ineligible" in auth_header or "test-groq-403" in auth_header or "groq-blocked-403" in self.headers.get("X-Model-Name", ""):
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("x-request-id", "req_groq_403_ineligible")
            self.end_headers()
            err = {
                "error": {
                    "message": "Your organization is not eligible to use this model. Some providers require accepting terms, adding billing or credits in their console.",
                    "type": "forbidden",
                    "code": "organization_restricted"
                }
            }
            self.wfile.write(json.dumps(err).encode("utf-8"))
            return

        # Scenario: xAI 403 Insufficient Credits / Team License
        if "xai-nocredits" in auth_header or "test-xai-403" in auth_header:
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("x-request-id", "req_xai_403_nocredits")
            self.end_headers()
            err = {
                "code": "Forbidden",
                "error": "Your team is not eligible to use this model. Please add credits at console.x.ai"
            }
            self.wfile.write(json.dumps(err).encode("utf-8"))
            return

        # Scenario: 404 Decommissioned / Unknown Model
        if model_requested == "retired-model-v1" or "test-404" in auth_header or "retired-model-404" in self.headers.get("X-Model-Name", ""):
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("x-request-id", "req_404_retired")
            self.end_headers()
            err = {
                "error": {
                    "message": f"The model '{model_requested or self.headers.get('X-Model-Name', 'retired-model-v1')}' has been retired or does not exist for this key.",
                    "type": "invalid_request_error",
                    "code": "model_not_found"
                }
            }
            self.wfile.write(json.dumps(err).encode("utf-8"))
            return

        # Scenario: 429 Rate Limit with Retry-After
        if "test-429" in auth_header:
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", "4")
            self.send_header("x-request-id", "req_429_rate_limit")
            self.end_headers()
            err = {
                "error": {
                    "message": "Rate limit reached. Please wait before retrying.",
                    "type": "tokens_exceeded",
                    "code": "rate_limit_exceeded"
                }
            }
            self.wfile.write(json.dumps(err).encode("utf-8"))
            return

        # Scenario: 413 Payload Too Large
        if "test-413" in auth_header:
            self.send_response(413)
            self.send_header("Content-Type", "application/json")
            self.send_header("x-request-id", "req_413_payload_too_large")
            self.end_headers()
            err = {
                "error": {
                    "message": "Request entity too large for this model.",
                    "type": "invalid_request_error",
                    "code": "context_length_exceeded"
                }
            }
            self.wfile.write(json.dumps(err).encode("utf-8"))
            return

        # Scenario: 400 Vision / Params unsupported
        if "test-400-vision" in auth_header:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("x-request-id", "req_400_no_vision")
            self.end_headers()
            err = {
                "error": {
                    "message": "This model can't read images. Please select a multimodal model.",
                    "type": "invalid_request_error",
                    "code": "unsupported_media_type"
                }
            }
            self.wfile.write(json.dumps(err).encode("utf-8"))
            return

        # 3. Valid endpoints
        if path.endswith("/models"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("x-request-id", "req_models_list")
            self.end_headers()
            resp = {
                "object": "list",
                "data": [
                    {"id": "llama-3.3-70b-versatile", "object": "model"},
                    {"id": "llama-3.1-8b-instant", "object": "model"},
                    {"id": "mixtral-8x7b-32768", "object": "model"},
                    {"id": "grok-2-1212", "object": "model"},
                    {"id": "grok-2-vision-1212", "object": "model"}
                ]
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        if path.endswith("/chat/completions"):
            is_stream = bool(body_json.get("stream", False))
            self.send_response(200)
            self.send_header("x-request-id", "req_chat_ok")
            if is_stream:
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                tokens = ["Hello", " from", " Cloud", " Provider!"]
                for t in tokens:
                    chunk = {
                        "id": "chatcmpl-test",
                        "object": "chat.completion.chunk",
                        "choices": [{"delta": {"content": t}, "index": 0}]
                    }
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            else:
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                resp = {
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "Hello from Cloud Provider! Answer is Option A."
                            }
                        }
                    ]
                }
                self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        # Fallback 404
        self.send_response(404)
        self.end_headers()


class FakeCloudRunner:
    def __init__(self, host: str = "127.0.0.1", port: int = 11436):
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> bool:
        try:
            self.server = HTTPServer((self.host, self.port), FakeCloudRequestHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info("FakeCloud server running at http://%s:%d", self.host, self.port)
            return True
        except Exception as e:
            logger.error("Failed to start FakeCloud server on port %d: %s", self.port, e)
            return False

    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None
