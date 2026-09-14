from __future__ import annotations

from pathlib import Path

from app.config import Settings


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
