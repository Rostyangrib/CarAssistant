from __future__ import annotations

from collections.abc import Callable
import logging
from time import perf_counter

from core.assistant import Assistant
from stt.base import AudioRecorder, SpeechToText, VoiceInputError


logger = logging.getLogger(__name__)


class VoiceInterface:
    def __init__(
        self,
        assistant: Assistant,
        recorder: AudioRecorder,
        stt: SpeechToText,
        *,
        debug: bool = False,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ) -> None:
        self.assistant = assistant
        self.recorder = recorder
        self.stt = stt
        self.debug = debug
        self.input = input_fn
        self.output = output_fn

    def run(self) -> None:
        self.output("Car AI Assistant started in voice mode.\n")
        self.output("Нажмите Enter и произнесите команду. Для выхода нажмите Ctrl+C.\n")
        while True:
            try:
                self.input("Нажмите Enter для начала записи...")
                self.process_once()
            except (EOFError, KeyboardInterrupt):
                self.output("\nДо встречи!")
                return

    def process_once(self) -> None:
        total_started = perf_counter()
        self.output("Listening...")
        try:
            audio = self.recorder.record_utterance()
            stt_started = perf_counter()
            transcription = self.stt.transcribe(audio)
            stt_latency = perf_counter() - stt_started
        except VoiceInputError as error:
            logger.exception("Recoverable voice input error")
            self.output(error.user_message)
            return
        text = transcription.text.strip()
        if not text:
            self.output("Не удалось распознать речь. Попробуйте ещё раз.")
            return
        self.output(f"You said: {text}")
        assistant_started = perf_counter()
        try:
            reply = self.assistant.handle(text)
        except Exception:
            logger.exception("Failed to process recognized command")
            self.output("Assistant: Не удалось выполнить команду.")
            return
        assistant_latency = perf_counter() - assistant_started
        if self.debug:
            self.output(
                "\n".join(
                    [
                        "[DEBUG] input=voice",
                        f"[DEBUG] audio_duration={audio.duration:.2f}s",
                        f"[DEBUG] speech_wait_latency={audio.speech_wait_latency:.2f}s",
                        f"[DEBUG] recording_stop_reason={audio.stop_reason}",
                        f"[DEBUG] stt_model={getattr(self.stt, 'model_name', 'unknown')}",
                        f"[DEBUG] stt_device={getattr(self.stt, 'device', 'unknown')}",
                        f"[DEBUG] compute_type={getattr(self.stt, 'compute_type', 'unknown')}",
                        f"[DEBUG] transcription={text!r}",
                        f"[DEBUG] stt_latency={stt_latency:.2f}s",
                        f"[DEBUG] route={reply.route.value}",
                        f"[DEBUG] assistant_latency={assistant_latency:.2f}s",
                        f"[DEBUG] total_voice_request_latency={perf_counter() - total_started:.2f}s",
                    ]
                )
            )
        self.output(f"Assistant: {reply.text}")
