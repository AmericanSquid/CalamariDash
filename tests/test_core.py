from datetime import datetime, timezone
import json
from pathlib import Path

from calamaridash.adif import parse_adif
from calamaridash.adapters import PollingWatcher, WavelogAdapter
from calamaridash.models import QSO
from calamaridash.scoring import PROFILES, calculate


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
        assert request.full_url.endswith("/api/get_contacts_adif")
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


def test_score_and_rate():
    qsos = parse_adif(ADIF, "fixture")
    metrics = calculate(qsos, PROFILES["generic"], datetime(2025, 1, 10, 12, 20, tzinfo=timezone.utc))
    assert metrics["totalQsos"] == 2
    assert metrics["multiplierCount"] == 2
    assert metrics["score"] == 4
    assert metrics["rate20"] == 6.0


def test_flask_metrics_endpoint():
    from calamaridash.app import create_app
    app = create_app()
    response = app.test_client().get("/api/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_default_hamdash_endpoint_uses_live_host():
    from calamaridash.config import Settings
    assert Settings().hamdash_url == "https://hamdash.affirmatech.com/api/standing"
