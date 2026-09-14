from __future__ import annotations

import asyncio
import logging
from typing import Any

from .server import create_server
from .tools.music import MusicTools


logger = logging.getLogger(__name__)


class MCPGateway:
    """Synchronous application adapter over the real FastMCP tool dispatcher."""

    def __init__(self, tools: MusicTools) -> None:
        self.tools = tools
        self.server = create_server(tools)

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, object]:
        logger.debug("MCP call: name=%s arguments=%s", name, arguments or {})
        try:
            _, structured = asyncio.run(self.server.call_tool(name, arguments or {}))
        except Exception as error:
            logger.exception("MCP call failed")
            return {"success": False, "error": "mcp_error", "detail": str(error)}
        if not isinstance(structured, dict):
            logger.error("MCP returned no structured result for %s", name)
            return {"success": False, "error": "mcp_error"}
        return structured
