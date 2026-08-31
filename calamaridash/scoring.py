from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from .models import QSO


@dataclass(frozen=True)
class ScoringProfile:
    name: str
    points_per_qso: Callable[[QSO], int] = lambda qso: 1
    multiplier_key: Callable[[QSO], str] = lambda qso: qso.state or qso.section or qso.dxcc or qso.country
    contact_key: Callable[[QSO], str] = lambda qso: qso.dedupe_key
    exact: bool = False


def _rtty_multiplier(qso: QSO) -> str:
    # ARRL RTTY Roundup counts US states/DC, Canadian provinces/territories,
    # and non-US/non-Canadian DXCC entities once each, not once per band.
    if qso.state:
        return f"STATE:{qso.state}"
    if qso.dxcc and qso.dxcc not in {"291", "1"}:
        return f"DXCC:{qso.dxcc}"
    return ""


def _contest_contact_key(qso: QSO) -> str:
    return f"{qso.callsign.upper()}|{qso.band.upper()}"


PROFILES = {
    "arrl_rtty_roundup": ScoringProfile("ARRL RTTY Roundup", multiplier_key=_rtty_multiplier,
                                         contact_key=_contest_contact_key, exact=True),
    "generic": ScoringProfile("Generic contest"),
}


def calculate(qsos: list[QSO], profile: ScoringProfile, now: datetime | None = None,
              operating_seconds: float | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    contacts = {}
    for qso in sorted(qsos, key=lambda q: q.timestamp):
        contacts.setdefault(profile.contact_key(qso), qso)
    scored_qsos = list(contacts.values())
    keys = {profile.multiplier_key(q).strip().upper() for q in scored_qsos if profile.multiplier_key(q).strip()}
    points = sum(profile.points_per_qso(q) for q in scored_qsos)
    def rate(minutes: int) -> float:
        cutoff = now - timedelta(minutes=minutes)
        return round(sum(q.timestamp >= cutoff for q in scored_qsos) * 60 / minutes, 1)
    ordered = sorted(scored_qsos, key=lambda q: q.timestamp)
    if operating_seconds is not None:
        seconds = max(0, int(operating_seconds))
        operating = f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"
        hours = seconds / 3600
    elif len(ordered) < 2:
        operating = "00:00:00"
        hours = 0
    else:
        seconds = max(0, int((ordered[-1].timestamp - ordered[0].timestamp).total_seconds()))
        operating = f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"
        hours = seconds / 3600
    return {"totalQsos": len(scored_qsos), "multiplierCount": len(keys), "totalQsoPoints": points,
            "score": points * len(keys), "rate20": rate(20), "rate60": rate(60),
            "totalOpTime": operating, "avgQsHr": round(len(scored_qsos) / max(hours, 1), 1),
            "score_exact": profile.exact,
            "score_profile": profile.name,
            "bands": sorted({q.band for q in scored_qsos if q.band}),
            "modes": sorted({q.mode for q in scored_qsos if q.mode}),
            "lastQso": _last_qso(ordered[-1]) if ordered else None}


def _last_qso(qso: QSO) -> dict:
    return {"callsign": qso.callsign, "date": qso.timestamp.isoformat(), "band": qso.band,
            "mode": qso.mode, "frequency": qso.frequency, "dxcc": qso.dxcc, "state": qso.state}
