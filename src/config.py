"""Application configuration using pydantic-settings."""

from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

# Round start dates for the 2026 NCAA Tournament.
# Each tuple: (round_code, first game date for that round).
_ROUND_SCHEDULE = [
    ("R64", date(2026, 3, 17)),          # First Four Mar 17-18, R64 proper Mar 19-20
    ("R32", date(2026, 3, 21)),
    ("S16", date(2026, 3, 26)),
    ("E8", date(2026, 3, 28)),
    ("F4", date(2026, 4, 4)),
    ("Championship", date(2026, 4, 6)),
]


def _detect_current_round() -> str:
    """Determine the current tournament round based on today's date (UTC)."""
    today = datetime.now(UTC).date()
    result = "R64"  # default before or at tournament start
    for round_code, start_date in _ROUND_SCHEDULE:
        if today >= start_date:
            result = round_code
    return result


class Settings(BaseSettings):
    kalshi_api_key_id: str = ""
    kalshi_private_key_path: Path = Path("./kalshi_demo.key")
    kalshi_base_url: str = "https://api.elections.kalshi.com/trade-api/v2"
    log_level: str = "INFO"

    # Output paths
    html_output_path: Path = Path("./docs/index.html")
    snapshot_dir: Path = Path("./data/snapshots")

    # Current tournament round — set to "auto" to detect from today's date.
    # Valid explicit values: R64, R32, S16, E8, F4, Championship
    current_round: str = "auto"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @model_validator(mode="after")
    def _resolve_auto_round(self):
        if self.current_round == "auto":
            self.current_round = _detect_current_round()
        return self


settings = Settings()
