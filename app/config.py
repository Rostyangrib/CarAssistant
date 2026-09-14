from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Load a small .env file without making configuration depend on dotenv."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True, slots=True)
class Settings:
    music_dir: Path
    database_path: Path
    log_level: str = "INFO"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout: float = 60.0

    @classmethod
    def load(cls, env_file: Path | None = None) -> "Settings":
        _load_dotenv(env_file or PROJECT_ROOT / ".env")
        return cls(
            music_dir=_resolve_path(os.getenv("MUSIC_DIR", "media/music")),
            database_path=_resolve_path(os.getenv("DATABASE_PATH", "data/music.db")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:4b"),
            ollama_timeout=float(os.getenv("OLLAMA_TIMEOUT", "60")),
        )
