from __future__ import annotations

from dataclasses import dataclass
import logging
from time import perf_counter

from llm.base import LLM, ToolCall
from llm.ollama import (
    OllamaInvalidResponseError,
    OllamaModelNotFoundError,
    OllamaUnavailableError,
)
from mcp_server.tools.music import ToolClient
from music_backend.service import MusicNotFoundError, MusicService
from player.local_player import PlayerError
from .command_router import CommandRouter, RouteType


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AssistantReply:
    text: str
    tool_call: ToolCall | None = None
    tool_result: dict[str, object] | None = None
    route: RouteType = RouteType.LLM
    router_latency: float = 0.0
    direct_latency: float | None = None
    llm_latency: float | None = None
    total_latency: float = 0.0
    model: str | None = None


class Assistant:
    def __init__(
        self,
        llm: LLM,
        gateway: ToolClient,
        router: CommandRouter | None = None,
        service: MusicService | None = None,
    ) -> None:
        self.llm = llm
        self.gateway = gateway
        self.router = router or CommandRouter()
        self.service = service or gateway.tools.service

    def handle(self, message: str) -> AssistantReply:
        total_started = perf_counter()
        router_started = perf_counter()
        route = self.router.route(message)
        router_latency = perf_counter() - router_started
        logger.debug("Router: route=%s latency=%.6fs", route.kind.value, router_latency)

        if route.kind is RouteType.DIRECT and route.tool_call is not None:
            direct_started = perf_counter()
            result = self._execute_direct(route.tool_call)
            direct_latency = perf_counter() - direct_started
            text = self._render(route.tool_call, result)
            return AssistantReply(
                text=text,
                tool_call=route.tool_call,
                tool_result=result,
                route=route.kind,
                router_latency=router_latency,
                direct_latency=direct_latency,
                total_latency=perf_counter() - total_started,
            )

        logger.debug("LLM request: %s", message)
        llm_started = perf_counter()
        try:
            decision = self.llm.chat(message)
        except OllamaModelNotFoundError:
            model = getattr(self.llm, "model", "qwen3:4b")
            return self._error_reply(
                f"Модель {model} не найдена. Установите её вручную: ollama pull {model}",
                router_latency, total_started, perf_counter() - llm_started,
            )
        except OllamaUnavailableError:
            return self._error_reply(
                "Локальная модель сейчас недоступна. Проверьте, запущен ли Ollama.",
                router_latency, total_started, perf_counter() - llm_started,
            )
        except OllamaInvalidResponseError:
            logger.exception("Invalid response from Ollama")
            return self._error_reply(
                "Локальная модель вернула некорректный ответ.",
                router_latency, total_started, perf_counter() - llm_started,
            )
        llm_latency = perf_counter() - llm_started
        logger.debug("LLM response: %s", decision)
        model = getattr(self.llm, "model", None)
        if isinstance(decision, str):
            return AssistantReply(
                decision, route=route.kind, router_latency=router_latency,
                llm_latency=llm_latency, total_latency=perf_counter() - total_started, model=model,
            )
        result = self.gateway.call(decision.name, decision.arguments)
        return AssistantReply(
            self._render(decision, result), decision, result, route.kind,
            router_latency, None, llm_latency, perf_counter() - total_started, model,
        )

    def _error_reply(
        self, text: str, router_latency: float, total_started: float, llm_latency: float
    ) -> AssistantReply:
        return AssistantReply(
            text=text, route=RouteType.LLM, router_latency=router_latency,
            llm_latency=llm_latency, total_latency=perf_counter() - total_started,
            model=getattr(self.llm, "model", None),
        )

    def _execute_direct(self, call: ToolCall) -> dict[str, object]:
        try:
            if call.name == "play_artist":
                return {
                    "success": True,
                    "track": self.service.play_artist(str(call.arguments["artist"])).as_dict(),
                }
            if call.name == "play_track":
                return {
                    "success": True,
                    "track": self.service.play_track(str(call.arguments["title"])).as_dict(),
                }
            if call.name == "pause_music":
                self.service.pause()
                return {"success": True}
            if call.name == "resume_music":
                self.service.resume()
                return {"success": True}
            if call.name == "next_track":
                return {"success": True, "track": self.service.next().as_dict()}
            if call.name == "previous_track":
                return {"success": True, "track": self.service.previous().as_dict()}
            if call.name == "change_volume":
                return {"success": True, "volume": self.service.change_volume(int(call.arguments["delta"]))}
            if call.name == "play_random":
                return {"success": True, "track": self.service.play_random().as_dict()}
            return {"success": False, "error": "unknown_command"}
        except MusicNotFoundError as error:
            return {"success": False, "error": f"{error.args[0]}_not_found"}
        except (PlayerError, ValueError) as error:
            logger.exception("Direct music command failed")
            return {"success": False, "error": "player_error", "detail": str(error)}
        except Exception as error:
            logger.exception("Unexpected direct command error")
            return {"success": False, "error": "internal_error", "detail": str(error)}

    @staticmethod
    def _render(call: ToolCall, result: dict[str, object]) -> str:
        if not result.get("success"):
            error = result.get("error")
            if error == "artist_not_found":
                return "Не нашла такого исполнителя."
            if error == "track_not_found":
                return "Не нашла такой трек."
            if error == "player_error":
                return "Не получилось запустить музыку."
            return "Не удалось выполнить команду."
        track = result.get("track")
        if call.name == "get_current_track":
            if not isinstance(track, dict):
                return "Сейчас ничего не играет."
            return f"Сейчас играет «{track['title']}» — {track['artist']}."
        if call.name == "search_artist":
            artists = result.get("artists")
            if isinstance(artists, list) and artists:
                return f"Нашла исполнителя: {artists[0]}."
            return "Не нашла такого исполнителя."
        if call.name == "search_track":
            tracks = result.get("tracks")
            if isinstance(tracks, list) and tracks:
                titles = ", ".join(f"«{item['title']}» — {item['artist']}" for item in tracks[:3])
                return f"Нашла: {titles}."
            return "Не нашла подходящих треков."
        if call.name in {"play_track", "play_artist", "play_random"} and isinstance(track, dict):
            return f"Включаю «{track['title']}» — {track['artist']}."
        messages = {
            "pause_music": "Пауза.",
            "resume_music": "Продолжаю.",
            "next_track": "Переключаю.",
            "previous_track": "Переключаю.",
            "set_volume": f"Громкость: {result.get('volume')}%.",
            "change_volume": f"Громкость: {result.get('volume')}%.",
        }
        return messages.get(call.name, "Готово.")
