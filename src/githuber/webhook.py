import hashlib
import hmac
import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GITHUB_EVENTS = {
    "check_suite",
    "status",
    "pull_request",
    "pull_request_review",
    "issue_comment",
    "pull_request_review_comment",
}
SLACK_PATH_PREFIX = "/slack"
SLACK_TIMESTAMP_TOLERANCE = 300


def github_signature_valid(secret, signature, body):
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def slack_signature_valid(secret, timestamp, signature, body):
    if not timestamp or abs(time.time() - int(timestamp)) > SLACK_TIMESTAMP_TOLERANCE:
        return False
    base = f"v0:{timestamp}:{body.decode()}".encode()
    expected = "v0=" + hmac.new(secret, base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class HttpServer:
    def __init__(self, port, github_secret, slack_secret, on_github_event, on_slack_command):
        self.port = port
        self.github_secret = github_secret.encode()
        self.slack_secret = slack_secret.encode()
        self.on_github_event = on_github_event
        self.on_slack_command = on_slack_command

    def start(self):
        server = ThreadingHTTPServer(("", self.port), self._handler())
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"http api listening on :{self.port}", flush=True)

    def _handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if self.path.startswith(SLACK_PATH_PREFIX):
                    self._slack(body)
                else:
                    self._github(body)

            def _github(self, body):
                if not outer.github_secret or not github_signature_valid(
                    outer.github_secret, self.headers.get("X-Hub-Signature-256", ""), body
                ):
                    self._respond(401)
                    return
                if self.headers.get("X-GitHub-Event", "") in GITHUB_EVENTS:
                    outer.on_github_event()
                self._respond(204)

            def _slack(self, body):
                if not outer.slack_secret or not slack_signature_valid(
                    outer.slack_secret,
                    self.headers.get("X-Slack-Request-Timestamp", ""),
                    self.headers.get("X-Slack-Signature", ""),
                    body,
                ):
                    self._respond(401)
                    return
                form = urllib.parse.parse_qs(body.decode())
                text = (form.get("text") or [""])[0]
                reply = outer.on_slack_command(text)
                payload = json.dumps({"response_type": "ephemeral", "text": reply}).encode()
                self._respond(200, payload, "application/json")

            def _respond(self, code, payload=b"", content_type="text/plain"):
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if payload:
                    self.wfile.write(payload)

            def log_message(self, *args):
                pass

        return Handler
