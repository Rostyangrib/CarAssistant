from __future__ import annotations

from core.assistant import AssistantReply
from cli.interface import CLI, HELP


class StubAssistant:
    def __init__(self, fail: bool = False) -> None:
        self.messages: list[str] = []
        self.fail = fail

    def handle(self, message: str) -> AssistantReply:
        self.messages.append(message)
        if self.fail:
            raise RuntimeError
        return AssistantReply("Ответ")


def _run(inputs: list[str], assistant=None) -> tuple[list[str], StubAssistant]:
    messages = iter(inputs)
    output: list[str] = []
    stub = assistant or StubAssistant()
    CLI(stub, input_fn=lambda _: next(messages), output_fn=output.append).run()
    return output, stub


def test_exit() -> None:
    output, stub = _run(["exit"])
    assert output[-1] == "До встречи!"
    assert stub.messages == []


def test_help_empty_and_regular_command() -> None:
    output, stub = _run(["", "help", "привет", "exit"])
    assert HELP in output
    assert "Assistant: Ответ" in output
    assert stub.messages == ["привет"]


def test_error_is_user_friendly() -> None:
    output, _ = _run(["команда", "exit"], StubAssistant(fail=True))
    assert "Assistant: Не удалось выполнить команду." in output


def test_debug_output_contains_route_and_timing() -> None:
    messages = iter(["команда", "exit"])
    output: list[str] = []
    CLI(StubAssistant(), debug=True, input_fn=lambda _: next(messages), output_fn=output.append).run()
    debug = "\n".join(output)
    assert "route = llm" in debug
    assert "router =" in debug
    assert "total =" in debug
