from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigurationError(ValueError):
    """Raised when a configuration value cannot be used safely."""


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
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _positive_float(name: str, default: str) -> float:
    raw = os.getenv(name, default)
    try:
        value = float(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} должен быть числом, получено: {raw!r}") from error
    if value <= 0:
        raise ConfigurationError(f"{name} должен быть больше нуля")
    return value


def _positive_int(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        value = int(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} должен быть целым числом, получено: {raw!r}") from error
    if value <= 0:
        raise ConfigurationError(f"{name} должен быть больше нуля")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    music_dir: Path
    database_path: Path
    log_level: str = "INFO"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout: float = 60.0
    stt_model_path: Path = PROJECT_ROOT / "data/models/faster-whisper-small"
    stt_language: str = "ru"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    stt_beam_size: int = 1
    audio_input_device: str | int | None = None
    audio_sample_rate: int = 16_000
    audio_channels: int = 1
    audio_silence_threshold: float = 0.015
    audio_silence_duration: float = 1.0
    audio_speech_timeout: float = 8.0
    audio_max_record_seconds: float = 15.0

    @classmethod
    def load(cls, env_file: Path | None = None) -> "Settings":
        _load_dotenv(env_file or PROJECT_ROOT / ".env")
        raw_device = os.getenv("AUDIO_INPUT_DEVICE", "").strip()
        input_device: str | int | None = raw_device or None
        if raw_device.isdecimal():
            input_device = int(raw_device)
        sample_rate = _positive_int("AUDIO_SAMPLE_RATE", "16000")
        channels = _positive_int("AUDIO_CHANNELS", "1")
        if channels != 1:
            raise ConfigurationError("AUDIO_CHANNELS должен быть равен 1 для mono STT")
        silence_threshold = _positive_float("AUDIO_SILENCE_THRESHOLD", "0.015")
        if silence_threshold > 1:
            raise ConfigurationError("AUDIO_SILENCE_THRESHOLD должен быть не больше 1")
        return cls(
            music_dir=_resolve_path(os.getenv("MUSIC_DIR", "media/music")),
            database_path=_resolve_path(os.getenv("DATABASE_PATH", "data/music.db")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:4b"),
            ollama_timeout=_positive_float("OLLAMA_TIMEOUT", "60"),
            stt_model_path=_resolve_path(
                os.getenv("STT_MODEL_PATH", "data/models/faster-whisper-small")
            ),
            stt_language=os.getenv("STT_LANGUAGE", "ru").strip() or "ru",
            stt_device=os.getenv("STT_DEVICE", "cpu").strip() or "cpu",
            stt_compute_type=os.getenv("STT_COMPUTE_TYPE", "int8").strip() or "int8",
            stt_beam_size=_positive_int("STT_BEAM_SIZE", "1"),
            audio_input_device=input_device,
            audio_sample_rate=sample_rate,
            audio_channels=channels,
            audio_silence_threshold=silence_threshold,
            audio_silence_duration=_positive_float("AUDIO_SILENCE_DURATION", "1.0"),
            audio_speech_timeout=_positive_float("AUDIO_SPEECH_TIMEOUT", "8.0"),
            audio_max_record_seconds=_positive_float("AUDIO_MAX_RECORD_SECONDS", "15.0"),
        )
