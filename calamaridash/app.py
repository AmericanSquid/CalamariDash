import os
from datetime import datetime
from threading import Lock

from flask import Flask, jsonify, render_template, request

from .adapters import FLDigiAdapter, PollingWatcher, WavelogAdapter, WSJTXAdapter
from .config import Settings
from .contests import CONTESTS
from .hamdash import HamDashClient
from .session import ContestSession
from .scoring import PROFILES, calculate


def create_app(settings: Settings | None = None) -> Flask:
    app = Flask(__name__)
    initial_settings = settings or Settings.load()
    runtime = {"settings": initial_settings, "session": ContestSession.load(initial_settings.session_path,
                                                                            initial_settings.contest),
               "adapters": [], "watchers": [], "hamdash": None}
    state = {"source_qsos": {}, "qsos": [], "payload": {}, "last_upload": None}
    lock = Lock()

    def selected_profile(current):
        # The contest identifier is authoritative.  This prevents an ARRL
        # RTTY profile from accidentally being used for a phone contest.
        if current.contest.upper() == "ARRL-RTTY":
            return PROFILES["arrl_rtty_roundup"]
        return PROFILES["generic"]

    def recompute_and_upload(upload=True):
        current = runtime["settings"]
        profile = selected_profile(current)
        all_qsos = {q.dedupe_key: q for qsos in state["source_qsos"].values() for q in qsos}
        session = runtime["session"]
        if not session.active:
            state["qsos"] = []
        elif session.qso_started_at:
            start = datetime.fromisoformat(session.qso_started_at)
            state["qsos"] = sorted((q for q in all_qsos.values() if q.timestamp >= start), key=lambda q: q.timestamp)
        else:
            state["qsos"] = sorted(all_qsos.values(), key=lambda q: q.timestamp)
        timer_was_used = bool(session.qso_started_at or session.timer_running_since or session.elapsed_before_run)
        elapsed = session.elapsed_seconds() if timer_was_used else None
        metrics = calculate(state["qsos"], profile, operating_seconds=elapsed)
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
        state["payload"] = {**metrics, "lastQso": last, "contest": current.contest,
                             "score_warning": None if metrics["score_exact"] else
                             "Generic metrics only; official rules for this contest are not implemented."}
        runtime["hamdash"] = HamDashClient(current.hamdash_url, current.hamdash_api_key)
        if upload and runtime["hamdash"].upload(payload):
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
            watcher = PollingWatcher(adapter.read, lambda qsos, n=name, d=delta: update_source(n, qsos, d),
                                     interval=15 if name == "wavelog" else 2)
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

    @app.get("/api/session")
    def session_status():
        return jsonify(runtime["session"].public())

    @app.post("/api/session/start")
    def session_start():
        current = runtime["settings"]
        runtime["session"].start(current.contest)
        with lock:
            recompute_and_upload()
        return jsonify(runtime["session"].public())

    @app.post("/api/session/stop")
    def session_stop():
        runtime["session"].stop()
        with lock:
            recompute_and_upload()
        return jsonify(runtime["session"].public())

    @app.post("/api/session/end")
    def session_end():
        runtime["session"].end()
        with lock:
            state["source_qsos"] = {}
            recompute_and_upload(upload=False)
        return jsonify(runtime["session"].public())

    @app.get("/api/contests")
    def contests():
        return jsonify([{"code": code, "name": name} for code, name in CONTESTS])

    @app.get("/api/health")
    def health():
        source_status = []
        for adapter in runtime["adapters"]:
            source_status.append({"source": getattr(adapter, "source_name", adapter.__class__.__name__),
                                  "last_error": getattr(adapter, "last_error", None),
                                  "last_read_at": getattr(adapter, "last_read_at", None),
                                  "last_read_count": getattr(adapter, "last_read_count", 0),
                                  "path": getattr(adapter, "api_url", getattr(adapter, "path", None))})
        has_source_error = any(item["last_error"] for item in source_status)
        hamdash_error = runtime["hamdash"].last_error if runtime["hamdash"] else None
        return jsonify({"status": "degraded" if has_source_error or hamdash_error else "ok", "sources": len(runtime["adapters"]),
                       "last_upload": state["last_upload"], "hamdash_error": hamdash_error,
                       "score_warning": state["payload"].get("score_warning"),
                       "session": runtime["session"].public(), "source_status": source_status})

    @app.route("/api/settings", methods=["GET", "POST"])
    def settings_api():
        if request.method == "GET":
            return jsonify(runtime["settings"].public())
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Settings must be JSON."}), 400
        try:
            updated = runtime["settings"].updated(data)
            if (updated.contest != runtime["settings"].contest and runtime["session"].active
                    and state["qsos"]):
                return jsonify({"error": "End the current contest before changing its contest identifier."}), 409
            updated.save()
            runtime["settings"] = updated
            runtime["session"].contest = updated.contest
            runtime["session"].save()
            configure_sources()
        except OSError as error:
            return jsonify({"error": f"Could not save settings: {error}"}), 500
        return jsonify(runtime["settings"].public())

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
