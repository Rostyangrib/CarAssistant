from __future__ import annotations

from collections.abc import Callable
import logging
from time import perf_counter
from typing import Any

import numpy as np

from .base import (
    AudioData,
    AudioRecorder,
    MicrophoneNotFoundError,
    MicrophoneUnavailableError,
    SpeechNotDetectedError,
)


logger = logging.getLogger(__name__)


class SoundDeviceRecorder(AudioRecorder):
    """Push-to-talk recorder with a small RMS-based end-of-speech detector."""

    def __init__(
        self,
        *,
        input_device: str | int | None = None,
        sample_rate: int = 16_000,
        channels: int = 1,
        silence_threshold: float = 0.015,
        silence_duration: float = 1.0,
        speech_timeout: float = 8.0,
        max_record_seconds: float = 15.0,
        block_duration: float = 0.1,
        sounddevice_loader: Callable[[], Any] | None = None,
    ) -> None:
        self.input_device = input_device
        self.sample_rate = sample_rate
        self.channels = channels
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.speech_timeout = speech_timeout
        self.max_record_seconds = max_record_seconds
        self.block_duration = block_duration
        self._sounddevice_loader = sounddevice_loader or self._load_sounddevice

    @staticmethod
    def _load_sounddevice() -> Any:
        try:
            import sounddevice
        except ImportError as error:
            raise MicrophoneUnavailableError("sounddevice is not installed") from error
        return sounddevice

    def record_utterance(self) -> AudioData:
        sounddevice = self._sounddevice_loader()
        try:
            info = sounddevice.query_devices(self.input_device, "input")
        except Exception as error:
            logger.exception("Input device was not found: %r", self.input_device)
            raise MicrophoneNotFoundError(str(error)) from error
        if int(info.get("max_input_channels", 0)) < 1:
            raise MicrophoneNotFoundError("device has no input channels")

        block_size = max(1, int(self.sample_rate * self.block_duration))
        started = perf_counter()
        frames: list[np.ndarray] = []
        speech_started = False
        speech_started_at = 0.0
        silent_seconds = 0.0
        captured_seconds = 0.0
        stop_reason = "timeout"
        try:
            with sounddevice.InputStream(
                device=self.input_device,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=block_size,
            ) as stream:
                actual_rate = int(getattr(stream, "samplerate", self.sample_rate))
                logger.debug(
                    "Recording started: device=%r sample_rate=%d channels=%d",
                    self.input_device if self.input_device is not None else info.get("name", "default"),
                    actual_rate,
                    self.channels,
                )
                while captured_seconds < self.max_record_seconds:
                    frame, _overflowed = stream.read(block_size)
                    mono = np.asarray(frame, dtype=np.float32).reshape(-1)
                    frame_duration = len(mono) / self.sample_rate
                    captured_seconds += frame_duration
                    rms = float(np.sqrt(np.mean(np.square(mono), dtype=np.float64)))
                    if not speech_started:
                        if rms >= self.silence_threshold:
                            speech_started = True
                            speech_started_at = captured_seconds - frame_duration
                            frames.append(mono.copy())
                        elif captured_seconds >= self.speech_timeout:
                            raise SpeechNotDetectedError
                        continue
                    frames.append(mono.copy())
                    if rms < self.silence_threshold:
                        silent_seconds += frame_duration
                        if silent_seconds >= self.silence_duration:
                            stop_reason = "silence"
                            break
                    else:
                        silent_seconds = 0.0
                else:
                    stop_reason = "timeout"
        except KeyboardInterrupt:
            logger.debug("Recording stopped: reason=cancel")
            raise
        except SpeechNotDetectedError:
            logger.debug("Recording stopped: reason=no_speech")
            raise
        except Exception as error:
            logger.exception("Failed to open or read input device")
            raise MicrophoneUnavailableError(str(error)) from error

        if not speech_started:
            raise SpeechNotDetectedError
        samples = np.concatenate(frames).astype(np.float32, copy=False)
        audio = AudioData(
            samples=samples,
            sample_rate=self.sample_rate,
            channels=1,
            speech_wait_latency=speech_started_at,
            stop_reason=stop_reason,
        )
        logger.debug(
            "Recording stopped: reason=%s audio_duration=%.2fs wall_time=%.2fs",
            stop_reason,
            audio.duration,
            perf_counter() - started,
        )
        return audio


def list_input_devices(sounddevice_loader: Callable[[], Any] | None = None) -> list[str]:
    loader = sounddevice_loader or SoundDeviceRecorder._load_sounddevice
    sounddevice = loader()
    try:
        devices = sounddevice.query_devices()
    except Exception as error:
        raise MicrophoneUnavailableError(str(error)) from error
    result = []
    for index, device in enumerate(devices):
        if int(device.get("max_input_channels", 0)) > 0:
            result.append(
                f"{index}: {device.get('name', 'Unknown')} "
                f"(inputs={device['max_input_channels']}, default_rate={device.get('default_samplerate')})"
            )
    return result
