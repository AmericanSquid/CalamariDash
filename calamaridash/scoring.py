from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from .models import QSO


@dataclass(frozen=True)
class ScoringProfile:
    name: str
    points_per_qso: Callable[[QSO], int] = lambda qso: 1
    multiplier_key: Callable[[QSO], str] = lambda qso: qso.state or qso.section or qso.dxcc or qso.country


PROFILES = {
    "arrl_rtty_roundup": ScoringProfile("ARRL RTTY Roundup"),
    "generic": ScoringProfile("Generic contest"),
}


def calculate(qsos: list[QSO], profile: ScoringProfile, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    keys = {profile.multiplier_key(q).strip().upper() for q in qsos if profile.multiplier_key(q).strip()}
    points = sum(profile.points_per_qso(q) for q in qsos)
    def rate(minutes: int) -> float:
        cutoff = now - timedelta(minutes=minutes)
        return round(sum(q.timestamp >= cutoff for q in qsos) * 60 / minutes, 1)
    ordered = sorted(qsos, key=lambda q: q.timestamp)
    if len(ordered) < 2:
        operating = "00:00:00"
    else:
        seconds = max(0, int((ordered[-1].timestamp - ordered[0].timestamp).total_seconds()))
        operating = f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"
    hours = ((ordered[-1].timestamp - ordered[0].timestamp).total_seconds() / 3600) if len(ordered) > 1 else 0
    return {"totalQsos": len(qsos), "multiplierCount": len(keys), "totalQsoPoints": points,
            "score": points * len(keys), "rate20": rate(20), "rate60": rate(60),
            "totalOpTime": operating, "avgQsHr": round(len(qsos) / max(hours, 1), 1),
            "bands": sorted({q.band for q in qsos if q.band}), "modes": sorted({q.mode for q in qsos if q.mode}),
            "lastQso": _last_qso(ordered[-1]) if ordered else None}


def _last_qso(qso: QSO) -> dict:
    return {"callsign": qso.callsign, "date": qso.timestamp.isoformat(), "band": qso.band,
            "mode": qso.mode, "frequency": qso.frequency, "dxcc": qso.dxcc, "state": qso.state}
