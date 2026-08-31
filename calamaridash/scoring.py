"""Contest scoring profiles."""

import math
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Callable, Iterable

from .models import QSO

CUSTOM_MULTIPLIER_FIELDS = {"none", "state", "section", "dxcc", "country", "gridsquare", "exchange"}
CUSTOM_DUPLICATE_SCOPES = {"qso", "callsign", "callsign_band"}
CUSTOM_SCORE_FORMULAS = {"points_only", "points_times_multipliers"}


@dataclass(frozen=True)
class ScoringProfile:
    name: str
    points_per_qso: Callable[[QSO, dict], float] = lambda qso, context: 1
    multiplier_keys: Callable[[QSO, dict], Iterable[str]] = lambda qso, context: (qso.state or qso.section or qso.dxcc or qso.country,)
    contact_key: Callable[[QSO], str] = lambda qso: qso.dedupe_key
    eligible: Callable[[QSO, dict], bool] = lambda qso, context: True
    score_formula: Callable[[float, int, dict], float] = lambda points, multipliers, context: points * multipliers
    multiplier_count: Callable[[set[str], dict], int] = lambda keys, context: len(keys)
    exact: bool = False
    required_qso_fields: tuple[str, ...] = ()
    required_context: tuple[str, ...] = ()
    warning: str = ""


def _band(qso):
    return qso.band.strip().upper()


def _mode(qso):
    mode = qso.mode.strip().upper()
    if mode in {"PHONE", "SSB", "FM", "AM"}:
        return "PHONE"
    if mode in {"CW", "CWR"}:
        return "CW"
    return "DIGITAL"


def _domestic(qso):
    return qso.dxcc.strip() in {"291", "1"}


def _contact_band(qso):
    return f"{qso.callsign.upper()}|{_band(qso)}"


def _contact_mode(qso):
    return f"{qso.callsign.upper()}|{_mode(qso)}"


def _contact_band_mode(qso):
    return f"{qso.callsign.upper()}|{_band(qso)}|{_mode(qso)}"


def _scoped(value, qso, per_band=False, per_mode=False):
    value = value.strip().upper()
    if per_mode:
        value = f"{_mode(qso)}:{value}"
    if per_band:
        value = f"{_band(qso)}:{value}"
    return value


def _rtty_multiplier(qso, context):
    if qso.state:
        return (f"STATE:{qso.state}",)
    if qso.dxcc and not _domestic(qso):
        return (f"DXCC:{qso.dxcc}",)
    return ()


def _arrl10_multiplier(qso, context):
    values = []
    if qso.state:
        values.append(f"STATE:{qso.state}")
    elif qso.dxcc:
        values.append(f"DXCC:{qso.dxcc}")
    ituz = qso.raw.get("ITUZ") or qso.raw.get("ITU_ZONE")
    if ituz:
        values.append(f"ITU:{ituz}")
    return tuple(_scoped(value, qso, per_mode=True) for value in values)


def _arrl160_multiplier(qso, context):
    values = []
    if qso.section or qso.state:
        values.append(f"SECTION:{qso.section or qso.state}")
    if qso.dxcc:
        values.append(f"DXCC:{qso.dxcc}")
    return tuple(values)


def _arrl160_points(qso, context):
    return 2 if _domestic(qso) else 5


def _arrl_dx_eligible(qso, context):
    station_dxcc = str(context.get("station_dxcc", "291"))
    return bool(qso.dxcc) and (_domestic(qso) if station_dxcc not in {"291", "1"} else not _domestic(qso))


def _arrl_dx_multiplier(qso, context):
    station_dxcc = str(context.get("station_dxcc", "291"))
    if station_dxcc in {"291", "1"}:
        return (f"DXCC:{_band(qso)}:{qso.dxcc}",) if qso.dxcc else ()
    value = qso.section or qso.state
    return (f"SECTION:{_band(qso)}:{value}",) if value else ()


def _grid_center(grid):
    grid = str(grid or "").strip().upper()
    if len(grid) < 4:
        return None
    try:
        lon = (ord(grid[0]) - 65) * 20 - 180 + int(grid[2]) * 2 + ((ord(grid[4]) - 65) + 0.5) * 2 / 24 if len(grid) >= 6 else (ord(grid[0]) - 65) * 20 - 180 + int(grid[2]) * 2 + 1
        lat = (ord(grid[1]) - 65) * 10 - 90 + int(grid[3]) + ((ord(grid[5]) - 65) + 0.5) / 24 if len(grid) >= 6 else (ord(grid[1]) - 65) * 10 - 90 + 0.5
        return lat, lon
    except (IndexError, ValueError):
        return None


def _grid_distance(qso, context):
    own, worked = _grid_center(context.get("station_gridsquare")), _grid_center(qso.gridsquare)
    if not own or not worked:
        return 0
    lat1, lon1 = map(math.radians, own)
    lat2, lon2 = map(math.radians, worked)
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _arrl_digital_points(qso, context):
    return 1 + max(1, math.ceil(_grid_distance(qso, context) / 500))


def _field_day_points(qso, context):
    return 1 if _mode(qso) == "PHONE" else 2


def _field_day_multiplier(keys, context):
    try:
        return max(1, min(5, int(context.get("field_day_power_multiplier", 2))))
    except (TypeError, ValueError):
        return 2


def _field_day_score(points, multipliers, context):
    try:
        bonus = max(0, float(context.get("field_day_bonus_points", 0)))
    except (TypeError, ValueError):
        bonus = 0
    return points * multipliers + bonus


def _same_country(qso, context):
    station_dxcc = str(context.get("station_dxcc", "291"))
    return bool(qso.dxcc and qso.dxcc == station_dxcc) or bool(qso.country and qso.country.upper() == str(context.get("station_country", "USA")).upper())


def _same_continent(qso, context):
    return bool(qso.continent and qso.continent.upper() == str(context.get("station_continent", "NA")).upper())


def _cq_points(qso, context, rtty=False):
    if _same_country(qso, context):
        return 1 if rtty else 0
    if _same_continent(qso, context):
        return 2 if rtty else (2 if str(context.get("station_continent", "NA")).upper() == "NA" else 1)
    return 3


def _cq_ww_multiplier(qso, context, rtty=False):
    values = []
    if qso.cq_zone:
        values.append(f"ZONE:{_band(qso)}:{qso.cq_zone}")
    if qso.dxcc:
        values.append(f"DXCC:{_band(qso)}:{qso.dxcc}")
    if rtty and _domestic(qso) and qso.state:
        values.append(f"QTH:{_band(qso)}:{qso.state}")
    return values


def _prefix(callsign):
    call = callsign.upper().split("/")[-1]
    match = re.match(r"([A-Z]+)(\d+)", call)
    if match:
        return "".join(match.groups())
    match = re.match(r"([A-Z]{2,})", call)
    return f"{match.group(1)[:2]}0" if match else call


def _wpx_points(qso, context):
    scale = 1 if _band(qso) in {"10M", "15M", "20M"} else 2
    if _same_country(qso, context):
        return 1
    if _same_continent(qso, context):
        return (2 if str(context.get("station_continent", "NA")).upper() == "NA" else 1) * scale
    return 3 * scale


def _cq160_points(qso, context):
    if _same_country(qso, context):
        return 2
    return 5 if _same_continent(qso, context) else 10


def _cq160_multiplier(qso, context):
    if _domestic(qso) and (qso.state or qso.section):
        return (f"STATE:{qso.state or qso.section}",)
    return (f"DXCC:{qso.dxcc}",) if qso.dxcc else ()


def _cq_vhf_points(qso, context):
    return 2 if _band(qso) in {"2M", "144", "144MHZ"} else 1


def _cq_vhf_multiplier(qso, context):
    return (f"{_band(qso)}:{qso.gridsquare[:4].upper()}",) if qso.gridsquare else ()


def _rookie_points(qso, context):
    return 2 if str(qso.raw.get("ROOKIE", "")).upper() in {"1", "Y", "YES", "TRUE"} else 1


def validate_custom_profile(values):
    if not isinstance(values, dict):
        raise ValueError("Custom scoring rules must be an object.")
    code, name = str(values.get("code", "")).strip(), str(values.get("name", "")).strip()
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
    return {"code": code, "name": name, "points_per_qso": points, "multiplier_field": multiplier_field,
            "duplicate_scope": duplicate_scope, "score_formula": score_formula}


def custom_profile(values):
    spec = validate_custom_profile(values)
    contact_key = {"qso": lambda q: q.dedupe_key, "callsign": lambda q: q.callsign.upper()}.get(spec["duplicate_scope"], _contact_band)
    field_name = spec["multiplier_field"]
    multiplier_keys = lambda q, c: ("" if field_name == "none" else str(getattr(q, field_name, "") or "").strip(),)
    score = lambda points, multipliers, context: points if spec["score_formula"] == "points_only" else points * multipliers
    return ScoringProfile(f"Custom: {spec['name']}", lambda q, c: spec["points_per_qso"], multiplier_keys,
                          contact_key=contact_key, score_formula=score, warning="Custom scoring profile; verify its rules before treating the score as official.")


PROFILES = {
    "arrl_10": ScoringProfile("ARRL 10-Meter Contest", lambda q, c: 2 if _mode(q) == "PHONE" else 4, _arrl10_multiplier, _contact_mode, exact=True),
    "arrl_160": ScoringProfile("ARRL 160-Meter Contest", _arrl160_points, _arrl160_multiplier, lambda q: q.callsign.upper(), exact=True),
    "arrl_field_day": ScoringProfile("ARRL Field Day", _field_day_points, contact_key=_contact_band_mode, multiplier_count=_field_day_multiplier, score_formula=_field_day_score, exact=True),
    "arrl_digital": ScoringProfile("ARRL International Digital Contest", _arrl_digital_points, lambda q, c: (), _contact_band, score_formula=lambda p, m, c: p, exact=True, required_qso_fields=("gridsquare",), required_context=("station_gridsquare",), warning="Grid square data is required for ARRL Digital distance points."),
    "arrl_dx": ScoringProfile("ARRL International DX Contest", lambda q, c: 3, _arrl_dx_multiplier, _contact_band, _arrl_dx_eligible, exact=True, required_qso_fields=("dxcc",), required_context=("station_dxcc",)),
    "arrl_rtty_roundup": ScoringProfile("ARRL RTTY Roundup", multiplier_keys=_rtty_multiplier, contact_key=_contact_band, exact=True),
    "arrl_sweepstakes": ScoringProfile("ARRL Sweepstakes Contest", lambda q, c: 2, lambda q, c: (f"SECTION:{q.section or q.state}",) if (q.section or q.state) else (), lambda q: q.callsign.upper(), exact=True),
    "arrl_rookie": ScoringProfile("ARRL Rookie Roundup", _rookie_points, lambda q, c: tuple(x for x in (f"STATE:{q.state}" if q.state else "", f"DXCC:{q.dxcc}" if q.dxcc and not _domestic(q) else "") if x), _contact_band, exact=False, warning="Rookie/non-rookie exchange status is not present in every ADIF log."),
    "cq_160": ScoringProfile("CQ World Wide 160-Meter Contest", _cq160_points, _cq160_multiplier, lambda q: q.callsign.upper(), exact=True, required_qso_fields=("continent", "dxcc"), required_context=("station_dxcc",)),
    "cq_wpx": ScoringProfile("CQ WW WPX Contest", _wpx_points, lambda q, c: (f"PREFIX:{_prefix(q.callsign)}",), _contact_band, exact=True, required_qso_fields=("continent", "dxcc"), required_context=("station_dxcc", "station_continent")),
    "cq_ww": ScoringProfile("CQ Worldwide DX Contest", lambda q, c: _cq_points(q, c), lambda q, c: _cq_ww_multiplier(q, c), _contact_band, exact=True, required_qso_fields=("continent", "cq_zone", "dxcc"), required_context=("station_dxcc", "station_continent")),
    "cq_ww_rtty": ScoringProfile("CQ Worldwide RTTY DX Contest", lambda q, c: _cq_points(q, c, True), lambda q, c: _cq_ww_multiplier(q, c, True), _contact_band, exact=True, required_qso_fields=("continent", "cq_zone", "dxcc"), required_context=("station_dxcc", "station_continent")),
    "cq_vhf": ScoringProfile("CQ Worldwide VHF Contest", _cq_vhf_points, _cq_vhf_multiplier, _contact_band, exact=True, required_qso_fields=("gridsquare",)),
    "generic": ScoringProfile("Generic contest"),
}


PROFILE_BY_CONTEST = {
    "ARRL-10": "arrl_10", "ARRL-160": "arrl_160", "ARRL-FD": "arrl_field_day", "ARRL-DIGI": "arrl_digital",
    "ARRL-DX-CW": "arrl_dx", "ARRL-DX-SSB": "arrl_dx", "ARRL-RTTY": "arrl_rtty_roundup",
    "ARRL-SS-CW": "arrl_sweepstakes", "ARRL-SS-SSB": "arrl_sweepstakes", "ARRL-RR-CW": "arrl_rookie",
    "ARRL-RR-DIG": "arrl_rookie", "ARRL-RR-PH": "arrl_rookie", "CQ-160-CW": "cq_160", "CQ-160-SSB": "cq_160",
    "CQ-WPX-CW": "cq_wpx", "CQ-WPX-RTTY": "cq_wpx", "CQ-WPX-SSB": "cq_wpx", "CQ-WW-CW": "cq_ww",
    "CQ-WW-SSB": "cq_ww", "CQ-WW-RTTY": "cq_ww_rtty", "CQ-VHF-DIGI": "cq_vhf", "CQ-VHF-SSBCW": "cq_vhf",
}

MODE_BY_CONTEST = {
    "ARRL-10": "MIXED", "ARRL-DIGI": "DIGITAL", "ARRL-DX-CW": "CW", "ARRL-DX-SSB": "PHONE",
    "ARRL-RTTY": "DIGITAL", "ARRL-SS-CW": "CW", "ARRL-SS-SSB": "PHONE", "ARRL-RR-CW": "CW",
    "ARRL-RR-DIG": "DIGITAL", "ARRL-RR-PH": "PHONE", "CQ-160-CW": "CW", "CQ-160-SSB": "PHONE",
    "CQ-WPX-CW": "CW", "CQ-WPX-RTTY": "DIGITAL", "CQ-WPX-SSB": "PHONE", "CQ-WW-CW": "CW",
    "CQ-WW-RTTY": "DIGITAL", "CQ-WW-SSB": "PHONE", "CQ-VHF-DIGI": "DIGITAL", "CQ-VHF-SSBCW": "ANALOG",
}


def profile_for_contest(contest):
    code = str(contest).upper()
    profile_name = PROFILE_BY_CONTEST.get(code)
    if not profile_name:
        return PROFILES["generic"]
    profile = PROFILES[profile_name]
    expected = MODE_BY_CONTEST.get(code)
    if not expected or expected == "MIXED":
        return profile
    allowed = {"CW", "PHONE"} if expected == "ANALOG" else {expected}
    return replace(profile, name=f"{profile.name} ({expected.lower()})",
                   eligible=lambda q, c: _mode(q) in allowed and profile.eligible(q, c))


def calculate(qsos, profile, now=None, operating_seconds=None, context=None):
    now, context = now or datetime.now(timezone.utc), context or {}
    missing = [field for field in profile.required_context if not context.get(field)]
    contacts = {}
    for qso in sorted(qsos, key=lambda q: q.timestamp):
        if profile.eligible(qso, context):
            contacts.setdefault(profile.contact_key(qso), qso)
    scored_qsos = list(contacts.values())
    missing.extend(field for field in profile.required_qso_fields if scored_qsos and any(not getattr(q, field, "") for q in scored_qsos))
    keys = {str(key).strip().upper() for qso in scored_qsos for key in profile.multiplier_keys(qso, context) if str(key).strip()}
    points = sum(profile.points_per_qso(qso, context) for qso in scored_qsos)
    multiplier_count = profile.multiplier_count(keys, context)

    def rate(minutes):
        cutoff = now - timedelta(minutes=minutes)
        return round(sum(q.timestamp >= cutoff for q in scored_qsos) * 60 / minutes, 1)

    ordered = sorted(scored_qsos, key=lambda q: q.timestamp)
    if operating_seconds is not None:
        seconds, hours = max(0, int(operating_seconds)), operating_seconds / 3600
        operating = f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"
    elif len(ordered) < 2:
        operating, hours = "00:00:00", 0
    else:
        seconds = max(0, int((ordered[-1].timestamp - ordered[0].timestamp).total_seconds()))
        operating, hours = f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}", seconds / 3600
    exact = profile.exact and not missing
    warning = profile.warning if missing or not profile.exact else ""
    if missing and not profile.warning:
        warning = "Required scoring data is missing: " + ", ".join(sorted(set(missing))) + "."
    return {"totalQsos": len(scored_qsos), "multiplierCount": multiplier_count, "totalQsoPoints": points,
            "score": profile.score_formula(points, multiplier_count, context), "rate20": rate(20), "rate60": rate(60),
            "totalOpTime": operating, "avgQsHr": round(len(scored_qsos) / max(hours, 1), 1), "score_exact": exact,
            "score_profile": profile.name, "score_warning": warning or None, "bands": sorted({q.band for q in scored_qsos if q.band}),
            "modes": sorted({q.mode for q in scored_qsos if q.mode}), "lastQso": _last_qso(ordered[-1]) if ordered else None}


def _last_qso(qso):
    return {"callsign": qso.callsign, "date": qso.timestamp.isoformat(), "band": qso.band, "mode": qso.mode,
            "frequency": qso.frequency, "dxcc": qso.dxcc, "state": qso.state}
