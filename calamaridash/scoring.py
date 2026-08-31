from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Callable

from .models import QSO


CUSTOM_MULTIPLIER_FIELDS = {"none", "state", "section", "dxcc", "country", "gridsquare", "exchange"}
CUSTOM_DUPLICATE_SCOPES = {"qso", "callsign", "callsign_band"}
CUSTOM_SCORE_FORMULAS = {"points_only", "points_times_multipliers"}


@dataclass(frozen=True)
class ScoringProfile:
    name: str
    points_per_qso: Callable[[QSO], float] = lambda qso: 1
    multiplier_key: Callable[[QSO], str] = lambda qso: qso.state or qso.section or qso.dxcc or qso.country
    contact_key: Callable[[QSO], str] = lambda qso: qso.dedupe_key
    exact: bool = False
    score_formula: Callable[[float, int], float] = lambda points, multipliers: points * multipliers


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


def _custom_value(qso: QSO, field_name: str) -> str:
    if field_name == "none":
        return ""
    return str(getattr(qso, field_name, "") or "").strip()


def validate_custom_profile(values: dict) -> dict:
    if not isinstance(values, dict):
        raise ValueError("Custom scoring rules must be an object.")
    code = str(values.get("code", "")).strip()
    name = str(values.get("name", "")).strip()
    if not code or len(code) > 80:
        raise ValueError("Contest code or full name is required and must be 80 characters or fewer.")
    if not name or len(name) > 120:
        raise ValueError("Contest display name is required and must be 120 characters or fewer.")
    try:
        points = float(values.get("points_per_qso", 1))
    except (TypeError, ValueError):
        raise ValueError("Points per QSO must be a number.") from None
    if not isfinite(points) or points < 0 or points > 1000:
        raise ValueError("Points per QSO must be between 0 and 1000.")
    multiplier_field = str(values.get("multiplier_field", "none")).strip().lower()
    duplicate_scope = str(values.get("duplicate_scope", "callsign_band")).strip().lower()
    score_formula = str(values.get("score_formula", "points_times_multipliers")).strip().lower()
    if multiplier_field not in CUSTOM_MULTIPLIER_FIELDS:
        raise ValueError("Unsupported multiplier field.")
    if duplicate_scope not in CUSTOM_DUPLICATE_SCOPES:
        raise ValueError("Unsupported duplicate policy.")
    if score_formula not in CUSTOM_SCORE_FORMULAS:
        raise ValueError("Unsupported score formula.")
    if multiplier_field == "none" and score_formula != "points_only":
        raise ValueError("Choose points-only scoring when the contest has no multiplier field.")
    return {"code": code, "name": name, "points_per_qso": points,
            "multiplier_field": multiplier_field, "duplicate_scope": duplicate_scope,
            "score_formula": score_formula}


def custom_profile(values: dict) -> ScoringProfile:
    spec = validate_custom_profile(values)
    if spec["duplicate_scope"] == "qso":
        contact_key = lambda qso: qso.dedupe_key
    elif spec["duplicate_scope"] == "callsign":
        contact_key = lambda qso: qso.callsign.upper()
    else:
        contact_key = _contest_contact_key
    multiplier_field = spec["multiplier_field"]
    multiplier_key = lambda qso: _custom_value(qso, multiplier_field)
    if spec["score_formula"] == "points_only":
        score = lambda points, multipliers: points
    else:
        score = lambda points, multipliers: points * multipliers

    return ScoringProfile(
        f"Custom: {spec['name']}",
        points_per_qso=lambda qso: spec["points_per_qso"],
        multiplier_key=multiplier_key,
        contact_key=contact_key,
        exact=False,
        score_formula=score,
    )


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
            "score": profile.score_formula(points, len(keys)), "rate20": rate(20), "rate60": rate(60),
            "totalOpTime": operating, "avgQsHr": round(len(scored_qsos) / max(hours, 1), 1),
            "score_exact": profile.exact,
            "score_profile": profile.name,
            "bands": sorted({q.band for q in scored_qsos if q.band}),
            "modes": sorted({q.mode for q in scored_qsos if q.mode}),
            "lastQso": _last_qso(ordered[-1]) if ordered else None}


def _last_qso(qso: QSO) -> dict:
    return {"callsign": qso.callsign, "date": qso.timestamp.isoformat(), "band": qso.band,
            "mode": qso.mode, "frequency": qso.frequency, "dxcc": qso.dxcc, "state": qso.state}
