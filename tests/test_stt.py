from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from stt.base import AudioData, STTBackendError, STTModelNotFoundError
from stt.faster_whisper import FasterWhisperSTT


class FakeModel:
    def __init__(self, text: str = " Пауза ") -> None:
        self.text = text
        self.kwargs = None

    def transcribe(self, samples, **kwargs):
        self.kwargs = kwargs
        return iter([SimpleNamespace(text=self.text)]), SimpleNamespace(
            language="ru", duration=1.2, duration_after_vad=0.7
        )


def _audio() -> AudioData:
    return AudioData(np.zeros(16_000, dtype=np.float32), 16_000)


def test_model_is_lazy_local_and_transcription_is_adapted(tmp_path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    calls = []
    model = FakeModel()

    def factory(*args, **kwargs):
        calls.append((args, kwargs))
        return model

    stt = FasterWhisperSTT(model_dir, model_factory=factory)
    assert calls == []
    result = stt.transcribe(_audio())
    assert result.text == "Пауза"
    assert result.detected_language == "ru"
    assert result.audio_duration == 1.2
    assert result.speech_duration == 0.7
    assert calls[0][1]["local_files_only"] is True
    assert model.kwargs["language"] == "ru"
    assert model.kwargs["beam_size"] == 1


def test_empty_transcription_is_preserved(tmp_path) -> None:
    tmp_path.joinpath("model").mkdir()
    stt = FasterWhisperSTT(tmp_path / "model", model_factory=lambda *_a, **_kw: FakeModel("  "))
    assert stt.transcribe(_audio()).text == ""


def test_missing_model_never_calls_factory(tmp_path) -> None:
    called = False

    def factory(*_args, **_kwargs):
        nonlocal called
        called = True

    with pytest.raises(STTModelNotFoundError):
        FasterWhisperSTT(tmp_path / "missing", model_factory=factory).transcribe(_audio())
    assert called is False


def test_empty_model_directory_is_reported_as_missing(tmp_path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    with pytest.raises(STTModelNotFoundError):
        FasterWhisperSTT(model_dir).transcribe(_audio())


def test_backend_initialization_error_is_wrapped(tmp_path) -> None:
    tmp_path.joinpath("model").mkdir()

    def broken(*_args, **_kwargs):
        raise RuntimeError("backend error")

    with pytest.raises(STTBackendError):
        FasterWhisperSTT(tmp_path / "model", model_factory=broken).transcribe(_audio())
