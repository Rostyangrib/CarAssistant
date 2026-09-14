from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class AudioData:
    samples: NDArray[np.float32]
    sample_rate: int
    channels: int = 1
    speech_wait_latency: float = 0.0
    stop_reason: str = "unknown"

    @property
    def duration(self) -> float:
        return len(self.samples) / self.sample_rate if self.sample_rate else 0.0


@dataclass(frozen=True, slots=True)
class Transcription:
    text: str
    detected_language: str | None = None
    audio_duration: float | None = None
    speech_duration: float | None = None


class VoiceInputError(RuntimeError):
    user_message = "Не удалось обработать голосовой ввод."


class SpeechNotDetectedError(VoiceInputError):
    user_message = "Речь не обнаружена."


class MicrophoneNotFoundError(VoiceInputError):
    user_message = "Микрофон не найден. Проверьте устройство ввода."


class MicrophoneUnavailableError(VoiceInputError):
    user_message = "Не удалось открыть микрофон. Проверьте настройки устройства ввода."


class STTModelNotFoundError(VoiceInputError):
    def __init__(self, model_path: object) -> None:
        super().__init__(str(model_path))
        self.user_message = (
            f"Локальная модель распознавания речи не найдена: {model_path}\n"
            "Выполните: hf download Systran/faster-whisper-small "
            "--local-dir data/models/faster-whisper-small"
        )


class STTBackendError(VoiceInputError):
    user_message = "Не удалось запустить локальное распознавание речи."


class AudioRecorder(ABC):
    @abstractmethod
    def record_utterance(self) -> AudioData:
        raise NotImplementedError


class SpeechToText(ABC):
    @abstractmethod
    def transcribe(self, audio: AudioData) -> Transcription:
        raise NotImplementedError
