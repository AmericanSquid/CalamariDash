import os
from datetime import datetime
from threading import Lock

from flask import Flask, jsonify, render_template, request

from .adapters import FLDigiAdapter, PollingWatcher, WavelogAdapter, WSJTXAdapter
from .config import Settings
from .hamdash import HamDashClient
from .scoring import PROFILES, calculate


def create_app(settings: Settings | None = None) -> Flask:
    app = Flask(__name__)
    runtime = {"settings": settings or Settings.load(), "adapters": [], "watchers": []}
    state = {"source_qsos": {}, "qsos": [], "payload": {}, "last_upload": None}
    lock = Lock()

    def recompute_and_upload():
        current = runtime["settings"]
        profile = PROFILES.get(current.profile, PROFILES["generic"])
        all_qsos = {q.dedupe_key: q for qsos in state["source_qsos"].values() for q in qsos}
        state["qsos"] = sorted(all_qsos.values(), key=lambda q: q.timestamp)
        metrics = calculate(state["qsos"], profile)
        last = metrics.pop("lastQso")
        payload = {
            "contest": current.contest,
            "score": metrics["score"],
            "operator": {
                "callsign": current.operator_callsign,
                "name": current.operator_name,
                "band": last.get("band", "") if last else "",
                "mode": last.get("mode", "") if last else "",
                "rate20": metrics["rate20"],
                "rate60": metrics["rate60"],
                "frequency": last.get("frequency") if last else None,
            },
            "multiplierCount": metrics["multiplierCount"],
            "totalQsos": metrics["totalQsos"],
            "totalQsoPoints": metrics["totalQsoPoints"],
            "club": {"name": current.club_name},
            "software": "CalamariDash",
            "softwareVersion": "0.1.0",
            "modeCategory": "MIXED",
            "totalOpTime": metrics["totalOpTime"],
            "avgQsHr": str(metrics["avgQsHr"]),
            "firstQsoDate": state["qsos"][0].timestamp.isoformat() if state["qsos"] else None,
            "lastQso": last,
        }
        state["payload"] = {**metrics, "lastQso": last, "contest": current.contest}
        if HamDashClient(current.hamdash_url, current.hamdash_api_key).upload(payload):
            state["last_upload"] = datetime.now().isoformat()

    def update_source(name, qsos, delta=False):
        with lock:
            if delta:
                existing = {q.dedupe_key: q for q in state["source_qsos"].get(name, [])}
                existing.update({q.dedupe_key: q for q in qsos})
                state["source_qsos"][name] = list(existing.values())
            else:
                state["source_qsos"][name] = qsos
            recompute_and_upload()

    def configure_sources():
        for watcher in runtime["watchers"]:
            watcher.stop()
        runtime["adapters"], runtime["watchers"] = [], []
        with lock:
            state["source_qsos"] = {}
            state["qsos"], state["payload"] = [], {}
        current = runtime["settings"]
        sources = []
        if current.fldigi_log_path:
            sources.append(("fldigi", FLDigiAdapter(current.fldigi_log_path), False))
        if current.wsjtx_log_path:
            sources.append(("wsjtx", WSJTXAdapter(current.wsjtx_log_path), False))
        if current.wavelog_url and current.wavelog_api_key and current.wavelog_station_id:
            sources.append(("wavelog", WavelogAdapter(current.wavelog_url, current.wavelog_api_key,
                                                        current.wavelog_station_id, current.wavelog_state_path), True))
        for name, adapter, delta in sources:
            runtime["adapters"].append(adapter)
            try:
                update_source(name, adapter.read(), delta)
            except Exception:
                pass
            watcher = PollingWatcher(adapter.read, lambda qsos, n=name, d=delta: update_source(n, qsos, d))
            watcher.start()
            runtime["watchers"].append(watcher)
        app.extensions["watchers"] = runtime["watchers"]

    configure_sources()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/metrics")
    def metrics():
        with lock:
            return jsonify(state["payload"])

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "sources": len(runtime["adapters"]), "last_upload": state["last_upload"]})

    @app.route("/api/settings", methods=["GET", "POST"])
    def settings_api():
        if request.method == "GET":
            return jsonify(runtime["settings"].public())
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Settings must be JSON."}), 400
        try:
            updated = runtime["settings"].updated(data)
            updated.save()
            runtime["settings"] = updated
            configure_sources()
        except OSError as error:
            return jsonify({"error": f"Could not save settings: {error}"}), 500
        return jsonify(runtime["settings"].public())

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
