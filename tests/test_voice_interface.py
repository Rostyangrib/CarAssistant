from __future__ import annotations

import numpy as np

from cli.voice import VoiceInterface
from core.assistant import Assistant, AssistantReply
from llm.base import LLM
from mcp_server.tools.music import MusicTools, ToolGateway
from music_backend.service import MusicService
from stt.base import AudioData, MicrophoneUnavailableError, Transcription
from tests.conftest import FakePlayer


class FakeAssistant:
    def __init__(self) -> None:
        self.messages = []

    def handle(self, message: str) -> AssistantReply:
        self.messages.append(message)
        return AssistantReply("Пауза.")


class FakeRecorder:
    def __init__(self, results=None) -> None:
        self.results = iter(results or [_audio()])

    def record_utterance(self):
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        return result


class FakeSTT:
    model_name = "fake-small"
    device = "cpu"
    compute_type = "int8"

    def __init__(self, texts=None) -> None:
        self.texts = iter(texts or ["Пауза"])

    def transcribe(self, _audio):
        return Transcription(next(self.texts))


def _audio() -> AudioData:
    return AudioData(np.zeros(1600, dtype=np.float32), 16_000, stop_reason="silence")


def test_recognized_text_is_passed_unchanged_and_reply_is_printed() -> None:
    assistant = FakeAssistant()
    output = []
    VoiceInterface(assistant, FakeRecorder(), FakeSTT(["  Давай что-нибудь из Кино  "]), output_fn=output.append).process_once()
    assert assistant.messages == ["Давай что-нибудь из Кино"]
    assert "You said: Давай что-нибудь из Кино" in output
    assert "Assistant: Пауза." in output


def test_empty_transcription_does_not_call_assistant() -> None:
    assistant = FakeAssistant()
    output = []
    VoiceInterface(assistant, FakeRecorder(), FakeSTT([" "]), output_fn=output.append).process_once()
    assert assistant.messages == []
    assert "Не удалось распознать речь. Попробуйте ещё раз." in output


def test_recoverable_error_allows_next_phrase_and_ctrl_c_exits() -> None:
    assistant = FakeAssistant()
    output = []
    recorder = FakeRecorder([MicrophoneUnavailableError(), _audio()])
    prompts = iter(["", ""])

    def input_fn(_prompt):
        try:
            return next(prompts)
        except StopIteration:
            raise KeyboardInterrupt

    VoiceInterface(
        assistant, recorder, FakeSTT(["Пауза"]), input_fn=input_fn, output_fn=output.append
    ).run()
    assert MicrophoneUnavailableError.user_message in output
    assert assistant.messages == ["Пауза"]
    assert output[-1] == "\nДо встречи!"


def test_debug_output_has_voice_timings() -> None:
    output = []
    VoiceInterface(
        FakeAssistant(), FakeRecorder(), FakeSTT(), debug=True, output_fn=output.append
    ).process_once()
    debug = "\n".join(output)
    assert "[DEBUG] input=voice" in debug
    assert "[DEBUG] stt_latency=" in debug
    assert "[DEBUG] assistant_latency=" in debug
    assert "[DEBUG] total_voice_request_latency=" in debug


class ForbiddenLLM(LLM):
    def chat(self, message):
        raise AssertionError("direct voice command must bypass LLM")


def test_voice_uses_existing_assistant_direct_route(repository, tracks) -> None:
    repository.upsert(tracks[0])
    player = FakePlayer()
    player.play([tracks[0]])
    service = MusicService(repository, player)
    gateway = ToolGateway(MusicTools(service))
    assistant = Assistant(ForbiddenLLM(), gateway)
    output = []
    VoiceInterface(assistant, FakeRecorder(), FakeSTT(["Пауза"]), output_fn=output.append).process_once()
    assert player.paused is True
    assert "Assistant: Пауза." in output
