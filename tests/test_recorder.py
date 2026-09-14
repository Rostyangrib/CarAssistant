from __future__ import annotations

import numpy as np
import pytest

from stt.base import MicrophoneNotFoundError, MicrophoneUnavailableError, SpeechNotDetectedError
from stt.recorder import SoundDeviceRecorder, list_input_devices


class FakeStream:
    def __init__(self, frames, fail: bool = False) -> None:
        self.frames = iter(frames)
        self.fail = fail
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        self.closed = True

    def read(self, _block_size):
        if self.fail:
            raise RuntimeError("busy")
        return next(self.frames), False


class FakeSoundDevice:
    def __init__(self, frames=(), *, query_error: bool = False, stream_error: bool = False) -> None:
        self.query_error = query_error
        self.stream = FakeStream(frames, fail=stream_error)
        self.stream_kwargs = None

    def query_devices(self, device=None, kind=None):
        if self.query_error:
            raise RuntimeError("no device")
        if kind == "input":
            return {"name": "Fake mic", "max_input_channels": 1, "default_samplerate": 16000}
        return [
            {"name": "Speaker", "max_input_channels": 0, "default_samplerate": 48000},
            {"name": "Fake mic", "max_input_channels": 1, "default_samplerate": 16000},
        ]

    def InputStream(self, **kwargs):
        self.stream_kwargs = kwargs
        return self.stream


def _frame(value: float) -> np.ndarray:
    return np.array([[value]], dtype=np.float32)


def _recorder(fake: FakeSoundDevice, **overrides) -> SoundDeviceRecorder:
    options = dict(
        sample_rate=10,
        silence_threshold=0.5,
        silence_duration=0.2,
        speech_timeout=0.4,
        max_record_seconds=1.0,
        block_duration=0.1,
        sounddevice_loader=lambda: fake,
    )
    options.update(overrides)
    return SoundDeviceRecorder(**options)


def test_waits_for_speech_then_stops_after_silence() -> None:
    fake = FakeSoundDevice([_frame(0), _frame(0), _frame(1), _frame(1), _frame(0), _frame(0)])
    audio = _recorder(fake).record_utterance()
    assert audio.sample_rate == 10
    assert audio.channels == 1
    assert audio.speech_wait_latency == pytest.approx(0.2)
    assert audio.duration == pytest.approx(0.4)
    assert audio.stop_reason == "silence"
    assert fake.stream.closed
    assert fake.stream_kwargs["channels"] == 1


def test_speech_timeout_does_not_return_silence() -> None:
    fake = FakeSoundDevice([_frame(0)] * 4)
    with pytest.raises(SpeechNotDetectedError):
        _recorder(fake).record_utterance()
    assert fake.stream.closed


def test_maximum_duration_stops_continuous_speech() -> None:
    fake = FakeSoundDevice([_frame(1)] * 10)
    audio = _recorder(fake, max_record_seconds=0.4).record_utterance()
    assert audio.duration == pytest.approx(0.4)
    assert audio.stop_reason == "timeout"


def test_enter_signal_stops_recording_manually() -> None:
    fake = FakeSoundDevice([_frame(1)] * 10)
    checks = iter([False, False, True])
    audio = _recorder(fake).record_utterance(lambda: next(checks))
    assert audio.duration == pytest.approx(0.2)
    assert audio.stop_reason == "manual"
    assert fake.stream.closed


def test_device_errors_are_domain_errors_and_release_stream() -> None:
    with pytest.raises(MicrophoneNotFoundError):
        _recorder(FakeSoundDevice(query_error=True)).record_utterance()
    busy = FakeSoundDevice([_frame(1)], stream_error=True)
    with pytest.raises(MicrophoneUnavailableError):
        _recorder(busy).record_utterance()
    assert busy.stream.closed


def test_lists_only_input_devices() -> None:
    assert list_input_devices(lambda: FakeSoundDevice()) == [
        "1: Fake mic (inputs=1, default_rate=16000)"
    ]
