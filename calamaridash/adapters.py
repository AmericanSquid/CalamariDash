import json
import threading
import urllib.request
from datetime import datetime
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

    def read(self) -> list[QSO]:
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
        request = urllib.request.Request(self.url + "/api/get_contacts_adif", data=payload,
                                          headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.load(response)
        except Exception:
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
