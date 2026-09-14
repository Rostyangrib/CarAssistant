from __future__ import annotations

import logging
from pathlib import Path

from .config import PROJECT_ROOT


def configure_logging(debug: bool = False, level: str = "INFO") -> None:
    log_path = PROJECT_ROOT / "data" / "car_assistant.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(log_path, encoding="utf-8")]
    if debug:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.DEBUG if debug else getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
