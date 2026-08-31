import os
from dataclasses import dataclass


@dataclass
class Settings:
    # The live HamDash service is hosted on .com; the developer page currently
    # documents a .net hostname that does not resolve in deployed environments.
    hamdash_url: str = os.getenv("HAMDASH_API_URL", "https://hamdash.affirmatech.com/api/standing")
    hamdash_api_key: str = os.getenv("API_KEY", "")
    fldigi_log_path: str = os.getenv("FLDIGI_LOG_PATH", "")
    wsjtx_log_path: str = os.getenv("WSJTX_LOG_PATH", "")
    wavelog_url: str = os.getenv("WAVELOG_URL", "")
    wavelog_api_key: str = os.getenv("WAVELOG_API_KEY", "")
    wavelog_station_id: str = os.getenv("WAVELOG_STATION_ID", "")
    wavelog_state_path: str = os.getenv("WAVELOG_STATE_PATH", "wavelog-state.json")
    contest: str = os.getenv("CONTEST", "TEST")
    operator_callsign: str = os.getenv("OPERATOR_CALLSIGN", "K3AYV")
    operator_name: str = os.getenv("OPERATOR_NAME", "Matt")
    club_name: str = os.getenv("CLUB_NAME", "Northeast Maryland Amateur Radio Contest Society")
    profile: str = os.getenv("SCORING_PROFILE", "arrl_rtty_roundup")
