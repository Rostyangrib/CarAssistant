from __future__ import annotations

import struct
import wave

from stt.wav import load_wav


def test_wav_is_converted_to_mono_16khz(tmp_path) -> None:
    path = tmp_path / "stereo.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(8_000)
        wav.writeframes(b"".join(struct.pack("<hh", 1000, -1000) for _ in range(80)))
    audio = load_wav(path)
    assert audio.sample_rate == 16_000
    assert audio.channels == 1
    assert len(audio.samples) == 160
    assert audio.stop_reason == "file"
