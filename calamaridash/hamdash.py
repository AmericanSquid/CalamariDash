import json
import urllib.error
import urllib.request


class HamDashClient:
    def __init__(self, url: str, api_key: str):
        self.url, self.api_key = url, api_key
        self.last_error = None
        self.last_status = None

    def upload(self, payload: dict) -> bool:
        if not self.url or not self.api_key:
            self.last_error = "HamDash is not configured"
            return False
        request = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                          headers={"apiKey": self.api_key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                self.last_status = response.status
                self.last_error = None if 200 <= response.status < 300 else f"HamDash HTTP {response.status}"
                return 200 <= response.status < 300
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace").strip()
            self.last_status = error.code
            self.last_error = f"HamDash HTTP {error.code}: {detail[:240]}"
            return False
        except urllib.error.URLError as error:
            self.last_status = None
            self.last_error = f"HamDash connection failed: {error.reason}"
            return False
        except Exception as error:
            self.last_status = None
            self.last_error = f"HamDash request failed: {type(error).__name__}: {error}"
            return False
