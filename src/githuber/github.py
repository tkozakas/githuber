import json
import time
import urllib.error
import urllib.parse
import urllib.request

RATE_FLOOR = 20
MAX_BACKOFF = 900


class GitHub:
    def __init__(self, cfg):
        self.api = cfg.github_api
        self.token = cfg.github_token
        self.remaining = None
        self.reset_at = 0.0

    def get(self, path, params=None):
        self._wait_for_budget()
        url = f"{self.api}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "githuber",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                self._track(resp.headers)
                return json.load(resp)
        except urllib.error.HTTPError as e:
            self._track(e.headers)
            if e.code in (403, 429) and self.remaining == 0:
                self._sleep_until_reset()
                return self.get(path, params)
            raise

    def login(self):
        return self.get("/user")["login"]

    def search_prs(self, query):
        return self.get("/search/issues", {"q": query, "per_page": "50"}).get("items", [])

    def pull(self, repo, number):
        return self.get(f"/repos/{repo}/pulls/{number}")

    def check_runs(self, repo, sha):
        return self.get(f"/repos/{repo}/commits/{sha}/check-runs", {"per_page": "100"})

    def combined_status(self, repo, sha):
        return self.get(f"/repos/{repo}/commits/{sha}/status")

    def issue_comments(self, repo, number, since):
        return self.get(f"/repos/{repo}/issues/{number}/comments", {"since": since, "per_page": "100"})

    def review_comments(self, repo, number, since):
        return self.get(f"/repos/{repo}/pulls/{number}/comments", {"since": since, "per_page": "100"})

    def reviews(self, repo, number):
        return self.get(f"/repos/{repo}/pulls/{number}/reviews", {"per_page": "100"})

    def _track(self, headers):
        if headers is None or "X-RateLimit-Remaining" not in headers:
            return
        self.remaining = int(headers["X-RateLimit-Remaining"])
        self.reset_at = float(headers.get("X-RateLimit-Reset", 0))

    def _wait_for_budget(self):
        if self.remaining is not None and self.remaining < RATE_FLOOR:
            self._sleep_until_reset()

    def _sleep_until_reset(self):
        delay = min(max(self.reset_at - time.time(), 1), MAX_BACKOFF)
        print(f"github rate limit low, sleeping {int(delay)}s", flush=True)
        time.sleep(delay)
        self.remaining = None
