from __future__ import annotations

from io import BytesIO
import urllib.error

import pytest

from llm.base import ToolCall
from llm.ollama import (
    OllamaInvalidResponseError,
    OllamaLLM,
    OllamaModelNotFoundError,
    OllamaUnavailableError,
)


def test_successful_tool_call() -> None:
    captured: dict[str, object] = {}

    def transport(payload: dict[str, object]) -> dict[str, object]:
        captured.update(payload)
        return {
            "message": {
                "content": "",
                "thinking": "must never be exposed",
                "tool_calls": [{"function": {"name": "play_artist", "arguments": {"artist": "Кино"}}}],
            }
        }

    decision = OllamaLLM("http://localhost:11434", "qwen3:4b", transport=transport).chat("Давай Кино")
    assert decision == ToolCall("play_artist", {"artist": "Кино"})
    assert captured["model"] == "qwen3:4b"
    assert captured["think"] is False
    assert captured["stream"] is False
    assert captured["options"] == {"temperature": 0}
    assert captured["tools"]


def test_successful_text_response() -> None:
    llm = OllamaLLM("http://localhost:11434", "qwen3:4b", transport=lambda _: {"message": {"content": "Пока не умею."}})
    assert llm.chat("Поставь грустное") == "Пока не умею."


def test_textual_tool_call_from_small_model_is_safely_parsed() -> None:
    llm = OllamaLLM(
        "http://localhost:11434", "gemma4:e2b",
        transport=lambda _: {"message": {"content": 'play_artist с artist="Слава КПСС"'}},
    )
    assert llm.chat("Слава КПСС") == ToolCall("play_artist", {"artist": "Слава КПСС"})


def test_gemma_special_quote_tool_call_is_safely_parsed() -> None:
    content = 'search_artist{artist:<|"|>Big Baby Tape<|"|>}'
    llm = OllamaLLM(
        "http://localhost:11434", "gemma4:e2b",
        transport=lambda _: {"message": {"content": content}},
    )
    assert llm.chat("Big Baby Tape это исполнитель") == ToolCall(
        "search_artist", {"artist": "Big Baby Tape"}
    )


@pytest.mark.parametrize("content", ["pause_music{}", "pause_music()", "pause_music"])
def test_textual_no_argument_tool_call_is_safely_parsed(content: str) -> None:
    llm = OllamaLLM(
        "http://localhost:11434", "gemma4:e2b",
        transport=lambda _: {"message": {"content": content}},
    )
    assert llm.chat("стоп") == ToolCall("pause_music")


def test_arbitrary_text_is_not_treated_as_tool() -> None:
    content = 'python="import os"'
    llm = OllamaLLM("http://localhost:11434", "gemma4:e2b", transport=lambda _: {"message": {"content": content}})
    assert llm.chat("Запрос") == content


def test_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*args, **kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", unavailable)
    with pytest.raises(OllamaUnavailableError):
        OllamaLLM("http://localhost:11434", "qwen3:4b").chat("Привет")


def test_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*args, **kwargs):
        raise urllib.error.HTTPError(
            "http://localhost:11434/api/chat", 404, "Not Found", {},
            BytesIO(b'{"error":"model qwen3:4b not found"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", missing)
    with pytest.raises(OllamaModelNotFoundError):
        OllamaLLM("http://localhost:11434", "qwen3:4b").chat("Привет")


@pytest.mark.parametrize(
    "response",
    [{}, {"message": {}}, {"message": {"tool_calls": [{"function": {"name": "shell", "arguments": {}}}]}}],
)
def test_invalid_response(response: dict[str, object]) -> None:
    llm = OllamaLLM("http://localhost:11434", "qwen3:4b", transport=lambda _: response)
    with pytest.raises(OllamaInvalidResponseError):
        llm.chat("Команда")
