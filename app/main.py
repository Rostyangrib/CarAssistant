from __future__ import annotations

import argparse
from pathlib import Path
import logging
from time import perf_counter

from cli.interface import CLI
from core.assistant import Assistant
from llm.mock import MockLLM
from llm.ollama import OllamaLLM
from mcp_server.gateway import MCPGateway
from mcp_server.tools.music import MusicTools
from music_backend.database import Database
from music_backend.repository import MusicRepository
from music_backend.scanner import MusicScanner
from music_backend.service import MusicService
from player.local_player import WindowsMediaPlayer
from .config import ConfigurationError, Settings
from .logging_config import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local text car assistant")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--scan", action="store_true", help="scan the local MP3 library and exit")
    modes.add_argument("--voice", action="store_true", help="use push-to-talk voice input")
    modes.add_argument(
        "--list-audio-devices", action="store_true", help="list input devices and exit"
    )
    modes.add_argument(
        "--transcribe-file", type=Path, metavar="WAV", help="transcribe a local WAV and exit"
    )
    parser.add_argument("--debug", action="store_true", help="show tool decisions and detailed logs")
    parser.add_argument("--mock", action="store_true", help="use deterministic mock LLM instead of Ollama")
    parser.add_argument("--audio-device", help="input device index or name (voice mode only)")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.audio_device is not None and not args.voice:
        parser.error("--audio-device можно использовать только вместе с --voice")
    try:
        settings = Settings.load()
    except ConfigurationError as error:
        parser.error(str(error))
    configure_logging(args.debug, settings.log_level)

    if args.list_audio_devices:
        from stt.base import VoiceInputError
        from stt.recorder import list_input_devices

        try:
            devices = list_input_devices()
        except VoiceInputError as error:
            print(error.user_message)
            return 1
        if not devices:
            print("Микрофон не найден. Проверьте устройство ввода.")
            return 1
        print("Доступные устройства ввода:")
        print("\n".join(devices))
        return 0

    if args.transcribe_file is not None:
        from stt.base import VoiceInputError
        from stt.faster_whisper import FasterWhisperSTT
        from stt.wav import load_wav

        stt = FasterWhisperSTT(
            settings.stt_model_path,
            language=settings.stt_language,
            device=settings.stt_device,
            compute_type=settings.stt_compute_type,
            beam_size=settings.stt_beam_size,
        )
        try:
            audio = load_wav(args.transcribe_file, settings.audio_sample_rate)
            started = perf_counter()
            transcription = stt.transcribe(audio)
            latency = perf_counter() - started
        except VoiceInputError as error:
            logging.getLogger(__name__).exception("File transcription failed")
            print(error.user_message)
            return 1
        text = transcription.text.strip()
        print(f"You said: {text}" if text else "Не удалось распознать речь.")
        if args.debug:
            print(f"[DEBUG] audio_duration={audio.duration:.2f}s")
            print(f"[DEBUG] stt_latency={latency:.2f}s")
        return 0

    database = Database(settings.database_path)
    database.initialize()
    repository = MusicRepository(database)
    if args.scan:
        print("Scanning music library...")
        result = MusicScanner(repository).scan(settings.music_dir)
        print(f"Found: {result.found} tracks")
        print(f"Added: {result.added}")
        print(f"Updated: {result.updated}")
        print(f"Removed: {result.removed}")
        return 0
    gateway = MCPGateway(MusicTools(MusicService(repository, WindowsMediaPlayer())))
    llm = (
        MockLLM(gateway)
        if args.mock
        else OllamaLLM(settings.ollama_host, settings.ollama_model, settings.ollama_timeout)
    )
    assistant = Assistant(llm, gateway)
    if args.voice:
        from cli.voice import VoiceInterface, windows_enter_pressed
        from stt.faster_whisper import FasterWhisperSTT
        from stt.recorder import SoundDeviceRecorder

        stt = FasterWhisperSTT(
            settings.stt_model_path,
            language=settings.stt_language,
            device=settings.stt_device,
            compute_type=settings.stt_compute_type,
            beam_size=settings.stt_beam_size,
        )
        raw_device = args.audio_device
        input_device = int(raw_device) if raw_device and raw_device.isdecimal() else raw_device
        if input_device is None:
            input_device = settings.audio_input_device
        recorder = SoundDeviceRecorder(
            input_device=input_device,
            sample_rate=settings.audio_sample_rate,
            channels=settings.audio_channels,
            silence_threshold=settings.audio_silence_threshold,
            silence_duration=settings.audio_silence_duration,
            speech_timeout=settings.audio_speech_timeout,
            max_record_seconds=settings.audio_max_record_seconds,
        )
        VoiceInterface(
            assistant,
            recorder,
            stt,
            debug=args.debug,
            stop_requested=windows_enter_pressed,
        ).run()
    else:
        CLI(assistant, debug=args.debug).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
