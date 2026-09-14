from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
from typing import Any

from .base import AudioData, SpeechToText, STTBackendError, STTModelNotFoundError, Transcription


logger = logging.getLogger(__name__)


class FasterWhisperSTT(SpeechToText):
    def __init__(
        self,
        model_path: Path,
        *,
        language: str = "ru",
        device: str = "cpu",
        compute_type: str = "int8",
        beam_size: int = 1,
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self._model_factory = model_factory
        self._model: Any | None = None

    @property
    def model_name(self) -> str:
        return self.model_path.name

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        if not self.model_path.is_dir():
            raise STTModelNotFoundError(str(self.model_path))
        factory = self._model_factory
        if factory is None:
            if not (self.model_path / "model.bin").is_file():
                raise STTModelNotFoundError(str(self.model_path))
            try:
                from faster_whisper import WhisperModel
            except ImportError as error:
                raise STTBackendError("faster-whisper is not installed") from error
            factory = WhisperModel
        try:
            self._model = factory(
                str(self.model_path),
                device=self.device,
                compute_type=self.compute_type,
                local_files_only=True,
            )
        except Exception as error:
            logger.exception("Failed to initialize faster-whisper")
            raise STTBackendError(str(error)) from error
        return self._model

    def transcribe(self, audio: AudioData) -> Transcription:
        model = self._load_model()
        try:
            segments, info = model.transcribe(
                audio.samples,
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=True,
            )
            text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        except Exception as error:
            logger.exception("faster-whisper transcription failed")
            raise STTBackendError(str(error)) from error
        return Transcription(
            text=text,
            detected_language=getattr(info, "language", None),
            audio_duration=getattr(info, "duration", audio.duration),
            speech_duration=getattr(info, "duration_after_vad", None),
        )
