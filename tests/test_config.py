from __future__ import annotations

from pathlib import Path

import pytest

from app.config import ConfigurationError, PROJECT_ROOT, Settings


def test_ollama_configuration_defaults(monkeypatch) -> None:
    for name in ("OLLAMA_HOST", "OLLAMA_MODEL", "OLLAMA_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.load(Path("missing.env"))
    assert settings.ollama_host == "http://localhost:11434"
    assert settings.ollama_model == "qwen3:4b"
    assert settings.ollama_timeout == 60.0


def test_ollama_configuration_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9999/")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "12")
    settings = Settings.load(Path("missing.env"))
    assert settings.ollama_host == "http://127.0.0.1:9999"
    assert settings.ollama_model == "qwen3:4b"
    assert settings.ollama_timeout == 12.0


def test_voice_configuration_defaults(monkeypatch) -> None:
    names = (
        "STT_MODEL_PATH", "STT_LANGUAGE", "STT_DEVICE", "STT_COMPUTE_TYPE",
        "STT_BEAM_SIZE", "AUDIO_INPUT_DEVICE", "AUDIO_SAMPLE_RATE", "AUDIO_CHANNELS",
        "AUDIO_SILENCE_THRESHOLD", "AUDIO_SILENCE_DURATION", "AUDIO_SPEECH_TIMEOUT",
        "AUDIO_MAX_RECORD_SECONDS",
    )
    for name in names:
        monkeypatch.delenv(name, raising=False)
    settings = Settings.load(Path("missing.env"))
    assert settings.stt_model_path == PROJECT_ROOT / "data/models/faster-whisper-small"
    assert settings.stt_language == "ru"
    assert settings.stt_device == "cpu"
    assert settings.stt_compute_type == "int8"
    assert settings.stt_beam_size == 1
    assert settings.audio_input_device is None
    assert settings.audio_sample_rate == 16_000
    assert settings.audio_channels == 1


def test_voice_configuration_device_and_validation(monkeypatch) -> None:
    monkeypatch.setenv("AUDIO_INPUT_DEVICE", "12")
    monkeypatch.setenv("AUDIO_SILENCE_THRESHOLD", "0")
    with pytest.raises(ConfigurationError, match="AUDIO_SILENCE_THRESHOLD"):
        Settings.load(Path("missing.env"))
    monkeypatch.setenv("AUDIO_SILENCE_THRESHOLD", "0.02")
    assert Settings.load(Path("missing.env")).audio_input_device == 12
