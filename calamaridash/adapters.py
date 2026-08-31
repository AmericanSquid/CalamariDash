import json
import threading
import urllib.request
import urllib.error
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path
from typing import Callable

from .adif import parse_adif, parse_adif_file
from .models import QSO


class ADIFFileAdapter:
    def __init__(self, path: str, source_name: str):
        self.path, self.source_name = path, source_name

    def read(self) -> list[QSO]:
        path = Path(self.path)
        return parse_adif_file(path) if path.exists() else []


class FLDigiAdapter(ADIFFileAdapter):
    def __init__(self, path: str):
        super().__init__(path, "fldigi")


class WSJTXAdapter(ADIFFileAdapter):
    def __init__(self, path: str):
        super().__init__(path, "wsjtx")


class WavelogAdapter:
    """Read-only delta reader for Wavelog's get_contacts_adif endpoint."""
    def __init__(self, url: str, api_key: str, station_id: str, state_path: str):
        self.url, self.api_key, self.station_id, self.state_path = url.rstrip("/"), api_key, station_id, Path(state_path)
        self.last_error = None
        parts = urlsplit(self.url)
        path = parts.path.rstrip("/")
        if not path.endswith("/index.php"):
            path += "/index.php"
        self.api_url = urlunsplit((parts.scheme, parts.netloc, path + "/api/get_contacts_adif", "", ""))

    def read(self) -> list[QSO]:
        self.last_error = None
        last_id = 0
        cached: dict[str, QSO] = {}
        if self.state_path.exists():
            try:
                saved = json.loads(self.state_path.read_text())
                last_id = saved.get("lastfetchedid", 0)
                for item in saved.get("qsos", []):
                    item["timestamp"] = datetime.fromisoformat(item["timestamp"])
                    cached[item["source_id"]] = QSO(**item)
            except (ValueError, OSError):
                pass
        payload = json.dumps({"key": self.api_key, "station_id": self.station_id, "fetchfromid": last_id}).encode()
        request = urllib.request.Request(self.api_url, data=payload,
                                          headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace").strip()
            self.last_error = f"Wavelog HTTP {error.code}: {detail[:240]}"
            return list(cached.values())
        except urllib.error.URLError as error:
            self.last_error = f"Wavelog connection failed: {error.reason}"
            return list(cached.values())
        except Exception as error:
            self.last_error = f"Wavelog request failed: {type(error).__name__}: {error}"
            return list(cached.values())
        new_id = data.get("lastfetchedid", last_id)
        for qso in parse_adif(data.get("adif", ""), "wavelog"):
            cached[qso.dedupe_key] = qso
        self.state_path.write_text(json.dumps({
            "lastfetchedid": new_id,
            "qsos": [{**qso.__dict__, "timestamp": qso.timestamp.isoformat(), "raw": {}} for qso in cached.values()],
        }))
        return list(cached.values())


class PollingWatcher:
    def __init__(self, read: Callable[[], list[QSO]], on_change: Callable[[list[QSO]], None], interval: float = 2):
        self.read, self.on_change, self.interval = read, on_change, interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._fingerprint: tuple[str, ...] = ()

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            try:
                qsos = self.read()
                fingerprint = tuple(q.dedupe_key for q in qsos)
                if fingerprint != self._fingerprint:
                    self._fingerprint = fingerprint
                    self.on_change(qsos)
            except Exception:
                pass
            self._stop.wait(self.interval)
