from __future__ import annotations

import pytest

from core.command_router import CommandRouter, RouteType


@pytest.mark.parametrize(
    ("message", "tool"),
    [
        ("Пауза", "pause_music"),
        ("Стоп", "pause_music"),
        ("Продолжи", "resume_music"),
        ("Следующий трек", "next_track"),
        ("Следующая песня", "next_track"),
        ("Предыдущий трек", "previous_track"),
        ("Громче", "change_volume"),
        ("Тише", "change_volume"),
        ("Включи музыку", "play_random"),
        ("Включи музыку любую", "play_random"),
    ],
)
def test_simple_commands_are_direct(message: str, tool: str) -> None:
    route = CommandRouter().route(message)
    assert route.kind is RouteType.DIRECT
    assert route.tool_call and route.tool_call.name == tool


@pytest.mark.parametrize(
    "message",
    ["Давай что-нибудь из Кино", "Я хочу послушать Linkin Park"],
)
def test_natural_commands_use_llm(message: str) -> None:
    assert CommandRouter().route(message).kind is RouteType.LLM


@pytest.mark.parametrize(
    ("message", "tool", "argument", "value"),
    [
        ("Включи исполнитель на Big Baby Tap", "play_artist", "artist", "big baby tap"),
        ("Ключи исполнителя Big Baby Tape", "play_artist", "artist", "big baby tape"),
        ("Респонитель Big Baby Tape", "play_artist", "artist", "big baby tape"),
        ("Песня Балаклава", "play_track", "title", "балаклава"),
    ],
)
def test_observed_stt_distortions_route_directly(message, tool, argument, value) -> None:
    route = CommandRouter().route(message)
    assert route.kind is RouteType.DIRECT
    assert route.tool_call and route.tool_call.name == tool
    assert route.tool_call.arguments[argument] == value
