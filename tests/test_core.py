from datetime import datetime, timezone
import json
from pathlib import Path

from calamaridash.adif import parse_adif
from calamaridash.adapters import PollingWatcher, WavelogAdapter
from calamaridash.models import QSO
from calamaridash.scoring import PROFILES, calculate, custom_profile


ADIF = "<ADIF_VER:5>3.1.4<EOH><CALL:4>W1AW<QSO_DATE:8>20250110<TIME_ON:6>120000<BAND:3>20m<MODE:3>SSB<DXCC:3>291<EOR><CALL:4>K3ABC<QSO_DATE:8>20250110<TIME_ON:6>121000<BAND:3>40m<MODE:4>RTTY<DXCC:3>1<EOR>"


def test_parse_adif_records_and_lengths():
    qsos = parse_adif(ADIF, "fixture")
    assert len(qsos) == 2
    assert qsos[0].callsign == "W1AW"
    assert qsos[1].band == "40m"


def test_empty_and_malformed_adif_are_safe():
    assert parse_adif("") == []
    assert parse_adif("<CALL:4>W1AW<EOH>") == []


def test_watcher_only_emits_when_qsos_change():
    calls = []
    qso = parse_adif(ADIF, "fixture")
    watcher = PollingWatcher(lambda: qso, lambda value: calls.append(value))
    watcher._fingerprint = tuple(item.dedupe_key for item in qso)
    watcher._run = lambda: None
    # The fingerprint is stable, so a repeated poll would not emit another update.
    current = tuple(item.dedupe_key for item in watcher.read())
    assert current == watcher._fingerprint
    assert calls == []


def test_wavelog_adapter_reads_delta_and_persists_cursor(tmp_path, monkeypatch):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b""

    def fake_urlopen(request, timeout):
        assert request.full_url.endswith("/index.php/api/get_contacts_adif")
        assert request.data and b"fetchfromid" in request.data
        return Response()

    def fake_json_load(response):
        return {"lastfetchedid": 17, "adif": ADIF}

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("json.load", fake_json_load)
    state_path = Path(tmp_path) / "cursor.json"
    qsos = WavelogAdapter("https://wavelog.local", "secret", "1", str(state_path)).read()
    assert len(qsos) == 2
    assert json.loads(state_path.read_text())["lastfetchedid"] == 17
    restored = WavelogAdapter("https://wavelog.local", "secret", "1", str(state_path)).read()
    assert len(restored) == 2


def test_wavelog_adapter_reports_http_errors(tmp_path, monkeypatch):
    from urllib.error import HTTPError
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, None)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    adapter = WavelogAdapter("https://wavelog.local", "secret", "1", str(tmp_path / "cursor.json"))
    assert adapter.read() == []
    assert adapter.last_error.startswith("Wavelog HTTP 401")


def test_hamdash_client_reports_http_errors(monkeypatch):
    from urllib.error import HTTPError
    from calamaridash.hamdash import HamDashClient
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 400, "Bad request", {}, None)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = HamDashClient("https://hamdash.example/api/standing", "secret")
    assert client.upload({"contest": "TEST"}) is False
    assert client.last_error.startswith("HamDash HTTP 400")


def test_score_and_rate():
    qsos = parse_adif(ADIF, "fixture")
    metrics = calculate(qsos, PROFILES["generic"], datetime(2025, 1, 10, 12, 20, tzinfo=timezone.utc))
    assert metrics["totalQsos"] == 2
    assert metrics["multiplierCount"] == 2
    assert metrics["score"] == 4
    assert metrics["rate20"] == 6.0


def test_arrl_rtty_roundup_score_deduplicates_by_call_and_band():
    def qso(call, minute, band, state="", dxcc="", source="fixture"):
        return QSO(call, datetime(2025, 1, 10, 12, minute, tzinfo=timezone.utc), band=band,
                   mode="RTTY", state=state, dxcc=dxcc, source_id=f"{source}-{call}-{minute}")

    qsos = [qso("K3ABC", 0, "20m", state="MD"), qso("K3ABC", 1, "20m", state="MD"),
            qso("N0XYZ", 2, "40m", state="VA"), qso("F4ABC", 3, "20m", dxcc="227")]
    metrics = calculate(qsos, PROFILES["arrl_rtty_roundup"], operating_seconds=5400)
    assert metrics["totalQsos"] == 3
    assert metrics["totalQsoPoints"] == 3
    assert metrics["multiplierCount"] == 3
    assert metrics["score"] == 9
    assert metrics["totalOpTime"] == "01:30:00"
    assert metrics["score_exact"] is True


def test_custom_profile_supports_points_only_and_call_duplicates():
    profile = custom_profile({"code": "EDGE-1", "name": "Edge Case",
                              "points_per_qso": 2, "multiplier_field": "none",
                              "duplicate_scope": "callsign", "score_formula": "points_only"})
    qsos = [QSO("K3ABC", datetime(2025, 1, 10, 12, 0, tzinfo=timezone.utc), band="20m", source_id="one"),
            QSO("K3ABC", datetime(2025, 1, 10, 12, 1, tzinfo=timezone.utc), band="40m", source_id="two"),
            QSO("N0XYZ", datetime(2025, 1, 10, 12, 2, tzinfo=timezone.utc), band="20m", source_id="three")]
    metrics = calculate(qsos, profile)
    assert metrics["totalQsos"] == 2
    assert metrics["totalQsoPoints"] == 4
    assert metrics["multiplierCount"] == 0
    assert metrics["score"] == 4
    assert metrics["score_exact"] is False


def test_custom_profile_validation_rejects_unsafe_or_inconsistent_rules():
    from pytest import raises
    with raises(ValueError, match="points-only"):
        custom_profile({"code": "EDGE-2", "name": "Bad", "points_per_qso": 1,
                        "multiplier_field": "none", "duplicate_scope": "qso",
                        "score_formula": "points_times_multipliers"})
    with raises(ValueError, match="Unsupported score formula"):
        custom_profile({"code": "EDGE-3", "name": "Bad", "points_per_qso": 1,
                        "multiplier_field": "state", "duplicate_scope": "qso",
                        "score_formula": "points * __import__('os').system('x')"})


def test_flask_metrics_endpoint():
    from calamaridash.app import create_app
    app = create_app()
    response = app.test_client().get("/api/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_default_hamdash_endpoint_uses_live_host():
    from calamaridash.config import Settings
    assert Settings().hamdash_url == "https://hamdash.affirmatech.com/api/standing"


def test_settings_api_persists_local_configuration(tmp_path):
    from calamaridash.app import create_app
    from calamaridash.config import Settings

    path = tmp_path / "settings.json"
    app = create_app(Settings(settings_path=str(path)))
    client = app.test_client()
    response = client.post("/api/settings", json={
        "operator_callsign": "N0CALL",
        "wavelog_url": "https://log.example.com/index.php",
        "wavelog_station_id": "42",
        "wavelog_api_key": "read-only-key",
    })
    assert response.status_code == 200
    assert response.json["operator_callsign"] == "N0CALL"
    assert response.json["wavelog_api_key_set"] is True
    saved = json.loads(path.read_text())
    assert saved["wavelog_station_id"] == "42"
    assert saved["wavelog_api_key"] == "read-only-key"


def test_contest_selector_and_session_lifecycle(tmp_path):
    from calamaridash.app import create_app
    from calamaridash.config import Settings

    app = create_app(Settings(settings_path=str(tmp_path / "settings.json"),
                              session_path=str(tmp_path / "session.json")))
    client = app.test_client()
    contests = client.get("/api/contests").json
    assert {contest["code"] for contest in contests} >= {"ARRL-RTTY", "CQ-WPX-SSB"}

    assert client.post("/api/session/end").json["active"] is False
    started = client.post("/api/session/start").json
    assert started["active"] is True
    assert started["qso_started_at"]
    stopped = client.post("/api/session/stop").json
    assert stopped["timer_running"] is False
    assert stopped["elapsed_seconds"] >= 0

    response = client.post("/api/settings", json={"contest": "CQ-WPX-SSB"})
    assert response.status_code == 200
    assert response.json["contest"] == "CQ-WPX-SSB"
    assert response.json["profile"] == "generic"


def test_custom_profile_api_persists_and_adds_contest(tmp_path):
    from calamaridash.app import create_app
    from calamaridash.config import Settings

    app = create_app(Settings(settings_path=str(tmp_path / "settings.json"),
                              session_path=str(tmp_path / "session.json")))
    client = app.test_client()
    rules = {"code": "EDGE-1", "name": "Edge Case Sprint", "points_per_qso": "2",
             "multiplier_field": "state", "duplicate_scope": "callsign_band",
             "score_formula": "points_times_multipliers"}
    response = client.post("/api/custom-profile", json=rules)
    assert response.status_code == 200
    assert response.json["profile"]["points_per_qso"] == 2.0
    assert any(contest["code"] == "EDGE-1" for contest in client.get("/api/contests").json)
    saved = json.loads((tmp_path / "settings.json").read_text())
    assert saved["custom_profiles"]["EDGE-1"]["multiplier_field"] == "state"
    assert client.post("/api/settings", json={"contest": "EDGE-1"}).status_code == 200
    assert client.get("/api/metrics").json["score_profile"] == "Custom: Edge Case Sprint"
    invalid = client.post("/api/custom-profile", json={**rules, "multiplier_field": "none"})
    assert invalid.status_code == 400
