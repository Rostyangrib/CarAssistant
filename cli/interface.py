from __future__ import annotations

from collections.abc import Callable
import json
import logging

from core.assistant import Assistant


logger = logging.getLogger(__name__)
HELP = "Команды: включи <трек/исполнителя>, случайная музыка, пауза, продолжи, следующий, предыдущий, громче, тише, громкость N, что сейчас играет?"


class CLI:
    def __init__(
        self,
        assistant: Assistant,
        debug: bool = False,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ) -> None:
        self.assistant = assistant
        self.debug = debug
        self.input = input_fn
        self.output = output_fn

    def run(self) -> None:
        self.output("Car AI Assistant started.\n")
        self.output('Type your command or "exit" to quit.\n')
        while True:
            try:
                message = self.input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                self.output("\nДо встречи!")
                return
            if message.casefold() in {"exit", "quit", "выход"}:
                self.output("До встречи!")
                return
            if message.casefold() in {"help", "помощь"}:
                self.output(HELP)
                continue
            if not message:
                continue
            try:
                reply = self.assistant.handle(message)
                if self.debug:
                    model = f"\nLLM:\n  model = {reply.model}" if reply.model else ""
                    tool = ""
                    if reply.tool_call:
                        tool = (
                            f"\nTool:\n  name = {reply.tool_call.name}"
                            f"\n  arguments = {json.dumps(reply.tool_call.arguments, ensure_ascii=False)}"
                            f"\n  result = {json.dumps(reply.tool_result, ensure_ascii=False)}"
                        )
                    timing = [f"  router = {reply.router_latency:.6f}s"]
                    if reply.direct_latency is not None:
                        timing.append(f"  direct = {reply.direct_latency:.6f}s")
                    if reply.llm_latency is not None:
                        timing.append(f"  llm = {reply.llm_latency:.6f}s")
                    timing.append(f"  total = {reply.total_latency:.6f}s")
                    self.output(
                        f"Router:\n  route = {reply.route.value}{model}{tool}\nTiming:\n" + "\n".join(timing)
                    )
                self.output(f"Assistant: {reply.text}")
            except Exception:
                logger.exception("Failed to process CLI command")
                self.output("Assistant: Не удалось выполнить команду.")
