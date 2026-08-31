import os
from threading import Lock
from flask import Flask, jsonify, render_template

from .adapters import FLDigiAdapter, PollingWatcher, WavelogAdapter, WSJTXAdapter
from .config import Settings
from .hamdash import HamDashClient
from .scoring import PROFILES, calculate


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings()
    app = Flask(__name__)
    state = {"qsos": [], "payload": {}, "last_upload": None}
    lock = Lock()
    client = HamDashClient(settings.hamdash_url, settings.hamdash_api_key)
    profile = PROFILES.get(settings.profile, PROFILES["generic"])

    def refresh(qsos):
        unique = {q.dedupe_key: q for q in qsos}
        with lock:
            state["qsos"] = sorted(unique.values(), key=lambda q: q.timestamp)
            metrics = calculate(state["qsos"], profile)
            last = metrics.pop("lastQso")
            payload = {"contest": settings.contest, "score": metrics["score"],
                       "operator": {"callsign": settings.operator_callsign, "name": settings.operator_name,
                                    "band": last.get("band", "") if last else "", "mode": last.get("mode", "") if last else "",
                                    "rate20": metrics["rate20"], "rate60": metrics["rate60"],
                                    "frequency": last.get("frequency") if last else None},
                       "multiplierCount": metrics["multiplierCount"], "totalQsos": metrics["totalQsos"],
                       "totalQsoPoints": metrics["totalQsoPoints"], "club": {"name": settings.club_name},
                       "software": "CalamariDash", "softwareVersion": "0.1.0", "modeCategory": "MIXED",
                       "totalOpTime": metrics["totalOpTime"], "avgQsHr": str(metrics["avgQsHr"]),
                       "firstQsoDate": state["qsos"][0].timestamp.isoformat() if state["qsos"] else None,
                       "lastQso": last}
            state["payload"] = {**metrics, "lastQso": last, "contest": settings.contest}
        if client.upload(payload):
            state["last_upload"] = __import__("datetime").datetime.now().isoformat()

    adapters = []
    if settings.fldigi_log_path: adapters.append(FLDigiAdapter(settings.fldigi_log_path))
    if settings.wsjtx_log_path: adapters.append(WSJTXAdapter(settings.wsjtx_log_path))
    if settings.wavelog_url and settings.wavelog_api_key and settings.wavelog_station_id:
        adapters.append(WavelogAdapter(settings.wavelog_url, settings.wavelog_api_key, settings.wavelog_station_id, settings.wavelog_state_path))
    for adapter in adapters:
        try: refresh(adapter.read())
        except Exception: pass
        watcher = PollingWatcher(adapter.read, refresh)
        watcher.start()
        app.extensions.setdefault("watchers", []).append(watcher)

    @app.get("/")
    def index(): return render_template("index.html")

    @app.get("/api/metrics")
    def metrics():
        with lock: return jsonify(state["payload"])

    @app.get("/api/health")
    def health(): return jsonify({"status": "ok", "sources": len(adapters), "last_upload": state["last_upload"]})
    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)

