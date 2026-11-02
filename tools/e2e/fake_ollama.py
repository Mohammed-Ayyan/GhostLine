"""
Fake Ollama Server for Ghostline E2E Testing.
Runs a lightweight loopback HTTP server emulating Ollama's REST API:
- GET  /api/tags
- POST /api/generate (streaming NDJSON & non-streaming)
- POST /api/chat (streaming NDJSON & non-streaming)
- GET  /api/version
- GET  /health
- Test control endpoints:
  - GET  /test/requests
  - POST /test/set_response
  - POST /test/clear
"""

import sys
import json
import time
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, List, Dict, Any

logger = logging.getLogger("fake_ollama")


class FakeOllamaHandler(BaseHTTPRequestHandler):
    server: "FakeOllamaServer"

    def log_message(self, format, *args):
        # Silence default stderr logging
        pass

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/api/tags", "/api/tags/"):
            self._send_json({
                "models": [
                    {"name": "phi3:mini", "model": "phi3:mini", "size": 2176179532},
                    {"name": "llama3.2:3b", "model": "llama3.2:3b", "size": 2019393189},
                    {"name": "custom-test-model", "model": "custom-test-model", "size": 1000000}
                ]
            })
        elif self.path in ("/api/version", "/api/version/"):
            self._send_json({"version": "0.3.14"})
        elif self.path in ("/health", "/", "/api/"):
            self._send_json({"status": "ok"})
        elif self.path == "/test/requests":
            self._send_json(self.server.recorded_requests)
        else:
            self._send_json({"error": "not found"}, status=404)

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_len) if content_len > 0 else b""
        body_str = body_bytes.decode("utf-8", errors="replace")
        
        req_data = {}
        if body_str:
            try:
                req_data = json.loads(body_str)
            except Exception:
                req_data = {"raw": body_str}

        # Record incoming request for assertions
        self.server.record_request({
            "path": self.path,
            "body": req_data,
            "timestamp": time.time()
        })

        if self.path == "/test/set_response":
            self.server.next_response = req_data.get("response", "Default fake answer.")
            self.server.token_delay_sec = float(req_data.get("token_delay", 0.01))
            self._send_json({"status": "configured"})
            return

        if self.path == "/test/clear":
            self.server.clear_history()
            self._send_json({"status": "cleared"})
            return

        if self.path in ("/api/generate", "/api/generate/"):
            prompt = req_data.get("prompt", "")
            is_stream = req_data.get("stream", True)
            
            # Formulate response
            if self.server.next_response:
                answer = self.server.next_response
            elif "capital of France" in prompt:
                answer = "The capital of France is Paris."
            elif "Senior Engineer" in prompt or "Staff" in prompt or "Alex Chen" in prompt:
                answer = "Based on your Senior Engineer background, the solution uses distributed consensus."
            else:
                answer = f"Verified answer for: {prompt[:30]}."

            if is_stream:
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.end_headers()

                # Stream word by word
                tokens = answer.split(" ")
                for i, token in enumerate(tokens):
                    suffix = " " if i < len(tokens) - 1 else ""
                    chunk = {"response": token + suffix, "done": False}
                    line = json.dumps(chunk) + "\n"
                    self.wfile.write(line.encode("utf-8"))
                    self.wfile.flush()
                    if self.server.token_delay_sec > 0:
                        time.sleep(self.server.token_delay_sec)

                # Final done chunk
                done_chunk = {"response": "", "done": True}
                self.wfile.write((json.dumps(done_chunk) + "\n").encode("utf-8"))
                self.wfile.flush()
            else:
                self._send_json({
                    "response": answer,
                    "done": True,
                    "model": req_data.get("model", "phi3:mini")
                })
            return

        if self.path in ("/api/chat", "/api/chat/"):
            answer = self.server.next_response or "Fake chat response."
            is_stream = req_data.get("stream", True)
            if is_stream:
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.end_headers()
                chunk = {"message": {"role": "assistant", "content": answer}, "done": True}
                self.wfile.write((json.dumps(chunk) + "\n").encode("utf-8"))
                self.wfile.flush()
            else:
                self._send_json({
                    "message": {"role": "assistant", "content": answer},
                    "done": True
                })
            return

        self._send_json({"error": "unsupported endpoint"}, status=404)


class FakeOllamaServer(HTTPServer):
    def __init__(self, host: str = "127.0.0.1", port: int = 11434):
        super().__init__((host, port), FakeOllamaHandler)
        self.recorded_requests: List[Dict[str, Any]] = []
        self.next_response: Optional[str] = None
        self.token_delay_sec: float = 0.01
        self._lock = threading.Lock()

    def record_request(self, req: Dict[str, Any]):
        with self._lock:
            self.recorded_requests.append(req)

    def clear_history(self):
        with self._lock:
            self.recorded_requests.clear()
            self.next_response = None


class FakeOllamaRunner:
    def __init__(self, host: str = "127.0.0.1", port: int = 11434):
        self.host = host
        self.port = port
        self.server: Optional[FakeOllamaServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        try:
            self.server = FakeOllamaServer(self.host, self.port)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info("Fake Ollama server running at http://%s:%d", self.host, self.port)
            return True
        except Exception as e:
            logger.error("Failed to start Fake Ollama server on %d: %s", self.port, e)
            return False

    def clear_history(self):
        if self.server:
            self.server.clear_history()

    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
            self.thread = None
        logger.info("Fake Ollama server stopped.")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11434
    runner = FakeOllamaRunner(port=port)
    if runner.start():
        print(f"Fake Ollama listening on 127.0.0.1:{port}. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            runner.stop()
