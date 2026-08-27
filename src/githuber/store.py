import json
import os


class Store:
    def __init__(self, path):
        self.path = path
        self.data = self._load()
        self.data.setdefault("prs", {})
        self.data.setdefault("mutes", [])
        self.data.setdefault("offset", 0)
        self.data.setdefault("disabled", [])

    @property
    def prs(self):
        return self.data["prs"]

    @property
    def mutes(self):
        return self.data["mutes"]

    @property
    def disabled(self):
        return self.data["disabled"]

    @property
    def offset(self):
        return self.data["offset"]

    @offset.setter
    def offset(self, value):
        self.data["offset"] = value

    def record(self, pr_key):
        return self.prs.setdefault(pr_key, {})

    def prune(self, live_keys):
        for key in list(self.prs):
            if key not in live_keys:
                del self.prs[key]

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f)
        os.replace(tmp, self.path)

    def _load(self):
        try:
            with open(self.path) as f:
                data = json.load(f)
                return data if isinstance(data, dict) and "prs" in data else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
