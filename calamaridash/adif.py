"""Small, tolerant ADIF reader used by all local and remote adapters."""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import QSO

TAG_RE = re.compile(r"<([^:>]+)(?::(\d+))?(?::[^>]*)?>", re.I)


def _timestamp(fields: dict[str, str]) -> datetime:
    date = fields.get("QSO_DATE") or fields.get("QSO_DATE_OFF")
    time = fields.get("TIME_OFF") or fields.get("TIME_ON") or "000000"
    if not date:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    time = re.sub(r"[^0-9]", "", time).ljust(6, "0")[:6]
    return datetime.strptime(date[:8] + time, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def parse_adif(text: str, source: str = "") -> list[QSO]:
    records: list[QSO] = []
    current: dict[str, str] = {}
    tags = list(TAG_RE.finditer(text))
    for index, match in enumerate(tags):
        name, length = match.group(1).upper(), match.group(2)
        start = match.end()
        if length is not None:
            value = text[start:start + int(length)]
        else:
            end = tags[index + 1].start() if index + 1 < len(tags) else len(text)
            value = text[start:end]
        value = value.strip()
        if name in {"EOH", "EOF"}:
            continue
        if name == "EOR":
            if current.get("CALL") and current.get("QSO_DATE"):
                records.append(_to_qso(current, source, len(records)))
            current = {}
        else:
            current[name] = value
    if current.get("CALL") and current.get("QSO_DATE"):
        records.append(_to_qso(current, source, len(records)))
    return records


def _to_qso(fields: dict[str, str], source: str, index: int) -> QSO:
    freq = fields.get("FREQ") or fields.get("FREQ_RX")
    try:
        frequency = float(freq) if freq else None
    except ValueError:
        frequency = None
    return QSO(
        callsign=fields["CALL"].strip(), timestamp=_timestamp(fields),
        band=fields.get("BAND", ""), mode=fields.get("MODE", ""), frequency=frequency,
        dxcc=fields.get("DXCC", ""), country=fields.get("COUNTRY", ""),
        state=fields.get("STATE", ""), section=fields.get("ARRL_SECT", ""),
        gridsquare=fields.get("GRIDSQUARE", ""),
        exchange=fields.get("STX_STRING") or fields.get("SRX_STRING", ""),
        source_id=f"{source}:{fields.get('QSO_DATE','')}:{fields.get('TIME_OFF', fields.get('TIME_ON',''))}:{fields['CALL']}:{index}",
        raw=fields, continent=fields.get("CONTINENT", ""),
        cq_zone=fields.get("CQZ") or fields.get("CQ_ZONE", ""),
    )


def parse_adif_file(path: str | Path) -> list[QSO]:
    return parse_adif(Path(path).read_text(encoding="utf-8", errors="replace"), str(path))
