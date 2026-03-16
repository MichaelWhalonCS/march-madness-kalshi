"""Application configuration using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kalshi_api_key_id: str = ""
    kalshi_private_key_path: Path = Path("./kalshi_demo.key")
    kalshi_base_url: str = "https://api.elections.kalshi.com/trade-api/v2"
    log_level: str = "INFO"

    # Output paths
    html_output_path: Path = Path("./docs/index.html")
    snapshot_dir: Path = Path("./data/snapshots")

    # Current tournament round (update as rounds complete)
    # Valid values: R64, R32, S16, E8, F4, Championship
    current_round: str = "R64"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
