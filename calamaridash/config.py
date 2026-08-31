import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    hamdash_url: str = os.getenv("HAMDASH_API_URL", "https://hamdash.affirmatech.com/api/standing")
    hamdash_api_key: str = os.getenv("API_KEY", "")
    fldigi_log_path: str = os.getenv("FLDIGI_LOG_PATH", "")
    wsjtx_log_path: str = os.getenv("WSJTX_LOG_PATH", "")
    wavelog_url: str = os.getenv("WAVELOG_URL", "")
    wavelog_api_key: str = os.getenv("WAVELOG_API_KEY", "")
    wavelog_station_id: str = os.getenv("WAVELOG_STATION_ID", "")
    wavelog_state_path: str = os.getenv("WAVELOG_STATE_PATH", "wavelog-state.json")
    contest: str = os.getenv("CONTEST", "ARRL-RTTY")
    operator_callsign: str = os.getenv("OPERATOR_CALLSIGN", "K3AYV")
    operator_name: str = os.getenv("OPERATOR_NAME", "Matt")
    club_name: str = os.getenv("CLUB_NAME", "Northeast Maryland Amateur Radio Contest Society")
    profile: str = os.getenv("SCORING_PROFILE", "arrl_rtty_roundup")
    settings_path: str = os.getenv("CALAMARIDASH_SETTINGS_PATH", "calamaridash-settings.json")
    session_path: str = os.getenv("CALAMARIDASH_SESSION_PATH", "calamaridash-session.json")
    custom_profiles: dict = field(default_factory=dict)

    @classmethod
    def load(cls):
        defaults = cls()
        path = Path(defaults.settings_path)
        if not path.exists():
            return defaults
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return defaults
        allowed = {field.name for field in fields(cls)}
        values = {**asdict(defaults), **{key: value for key, value in saved.items() if key in allowed}}
        if not isinstance(values.get("custom_profiles"), dict):
            values["custom_profiles"] = {}
        if str(values["contest"]).upper() == "ARRL-RTTY":
            values["profile"] = "arrl_rtty_roundup"
        elif values["profile"] == "arrl_rtty_roundup":
            values["profile"] = "generic"
        return cls(**values)

    def updated(self, values: dict):
        allowed = {field.name for field in fields(self)} - {"settings_path", "custom_profiles"}
        merged = asdict(self)
        for key in allowed:
            if key not in values:
                continue
            value = str(values[key]).strip()
            if key in {"hamdash_api_key", "wavelog_api_key"} and not value:
                continue
            merged[key] = value
        if merged["contest"].upper() == "ARRL-RTTY":
            merged["profile"] = "arrl_rtty_roundup"
        elif merged["profile"] == "arrl_rtty_roundup":
            merged["profile"] = "generic"
        return Settings(**merged)

    def with_custom_profile(self, code: str, profile: dict):
        merged = asdict(self)
        profiles = dict(self.custom_profiles or {})
        for existing in list(profiles):
            if str(existing).upper() == code.upper():
                del profiles[existing]
        profiles[code] = profile
        merged["custom_profiles"] = profiles
        return Settings(**merged)

    def save(self):
        path = Path(self.settings_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    def public(self) -> dict:
        data = asdict(self)
        if str(data["contest"]).upper() == "ARRL-RTTY":
            data["profile"] = "arrl_rtty_roundup"
        elif data["profile"] == "arrl_rtty_roundup":
            data["profile"] = "generic"
        data.pop("hamdash_api_key")
        data.pop("wavelog_api_key")
        data["hamdash_api_key_set"] = bool(self.hamdash_api_key)
        data["wavelog_api_key_set"] = bool(self.wavelog_api_key)
        return data
