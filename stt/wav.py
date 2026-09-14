from __future__ import annotations

from pathlib import Path
import wave

import numpy as np

from .base import AudioData, STTBackendError


def load_wav(path: Path, target_sample_rate: int = 16_000) -> AudioData:
    try:
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            raw = wav.readframes(wav.getnframes())
    except (OSError, wave.Error) as error:
        raise STTBackendError(f"Не удалось прочитать WAV: {path}") from error
    if sample_width == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sample_width == 2:
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 4:
        samples = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise STTBackendError(f"Неподдерживаемая разрядность WAV: {sample_width * 8} bit")
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if sample_rate != target_sample_rate and len(samples):
        target_length = round(len(samples) * target_sample_rate / sample_rate)
        old_positions = np.linspace(0.0, 1.0, len(samples), endpoint=False)
        new_positions = np.linspace(0.0, 1.0, target_length, endpoint=False)
        samples = np.interp(new_positions, old_positions, samples).astype(np.float32)
    return AudioData(np.asarray(samples, dtype=np.float32), target_sample_rate, 1, stop_reason="file")
