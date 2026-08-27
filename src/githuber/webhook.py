import hashlib
import hmac
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EVENTS = {
    "check_suite",
    "status",
    "pull_request",
    "pull_request_review",
    "issue_comment",
    "pull_request_review_comment",
}


class WebhookServer:
    def __init__(self, secret, port, wake):
        self.secret = secret.encode()
        self.port = port
        self.wake = wake

    def start(self):
        server = ThreadingHTTPServer(("", self.port), self._handler())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f"webhook listening on :{self.port}", flush=True)

    def _handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if not outer._valid(self.headers.get("X-Hub-Signature-256", ""), body):
                    self.send_response(401)
                    self.end_headers()
                    return
                if self.headers.get("X-GitHub-Event", "") in EVENTS:
                    outer.wake()
                self.send_response(204)
                self.end_headers()

            def log_message(self, *args):
                pass

        return Handler

    def _valid(self, signature, body):
        expected = "sha256=" + hmac.new(self.secret, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
