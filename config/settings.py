"""Environment-driven application settings."""

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read_port() -> int:
    """Read and validate the HTTP port from the environment."""
    raw_port = os.getenv("PORT", "8000")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("PORT must be an integer.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535.")
    return port


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable runtime settings loaded from environment variables."""

    port: int
    log_level: str
    data_folder: Path
    log_folder: Path
    database_url: str | None

    @property
    def tracking_file(self) -> Path:
        """Return the configured Excel tracking workbook path."""
        return self.data_folder / "EmailTracking.xlsx"


def load_settings() -> Settings:
    """Load settings, using project-local defaults for local development."""
    data_folder = Path(os.getenv("DATA_FOLDER", "data")).expanduser()
    if not data_folder.is_absolute():
        data_folder = PROJECT_ROOT / data_folder

    return Settings(
        port=_read_port(),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        data_folder=data_folder.resolve(),
        log_folder=PROJECT_ROOT / "logs",
        database_url=os.getenv("DATABASE_URL"),
    )
