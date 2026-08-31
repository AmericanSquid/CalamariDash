from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class QSO:
    callsign: str
    timestamp: datetime
    band: str = ""
    mode: str = ""
    frequency: float | None = None
    dxcc: str = ""
    country: str = ""
    state: str = ""
    section: str = ""
    gridsquare: str = ""
    exchange: str = ""
    source_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self):
        if self.timestamp.tzinfo is None:
            object.__setattr__(self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc))

    @property
    def dedupe_key(self) -> str:
        return self.source_id or "|".join((self.callsign.upper(), self.timestamp.isoformat(), self.band, self.mode))

