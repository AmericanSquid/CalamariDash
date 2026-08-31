import json
import urllib.request


class HamDashClient:
    def __init__(self, url: str, api_key: str):
        self.url, self.api_key = url, api_key

    def upload(self, payload: dict) -> bool:
        if not self.url or not self.api_key:
            return False
        request = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                          headers={"apiKey": self.api_key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return 200 <= response.status < 300
        except Exception:
            return False

