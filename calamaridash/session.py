import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _now():
    return datetime.now(timezone.utc)


@dataclass
class ContestSession:
    path: str
    active: bool = True
    qso_started_at: str | None = None
    timer_running_since: str | None = None
    elapsed_before_run: float = 0
    contest: str = "TEST"

    @classmethod
    def load(cls, path: str, contest: str):
        session = cls(path=path, contest=contest)
        file_path = Path(path)
        if not file_path.exists():
            return session
        try:
            values = json.loads(file_path.read_text(encoding="utf-8"))
            for key in ("active", "qso_started_at", "timer_running_since", "elapsed_before_run", "contest"):
                if key in values:
                    setattr(session, key, values[key])
            try:
                session.elapsed_before_run = max(0, float(session.elapsed_before_run))
            except (TypeError, ValueError):
                session.elapsed_before_run = 0
            session.active = bool(session.active)
            session.contest = str(session.contest or contest)
            for key in ("qso_started_at", "timer_running_since"):
                if cls._parse_timestamp(getattr(session, key)) is None:
                    setattr(session, key, None)
        except (OSError, ValueError, TypeError):
            pass
        return session

    def save(self):
        path = Path(self.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _parse_timestamp(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None

    def start(self, contest: str):
        self.contest = contest
        if not self.active:
            self.active = True
            self.qso_started_at = _now().isoformat()
            self.elapsed_before_run = 0
        if not self.timer_running_since:
            self.timer_running_since = _now().isoformat()
        self.save()

    def stop(self):
        if self.timer_running_since:
            started = self._parse_timestamp(self.timer_running_since)
            if started:
                self.elapsed_before_run += max(0, (_now() - started).total_seconds())
            self.timer_running_since = None
        self.save()

    def end(self):
        self.stop()
        self.active = False
        self.qso_started_at = None
        self.save()

    def elapsed_seconds(self) -> float:
        elapsed = self.elapsed_before_run
        if self.timer_running_since:
            started = self._parse_timestamp(self.timer_running_since)
            if started:
                elapsed += max(0, (_now() - started).total_seconds())
        return elapsed

    def public(self) -> dict:
        seconds = int(self.elapsed_seconds())
        return {
            "active": self.active,
            "contest": self.contest,
            "timer_running": bool(self.timer_running_since),
            "elapsed_seconds": seconds,
            "elapsed": f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}",
            "qso_started_at": self.qso_started_at,
        }
