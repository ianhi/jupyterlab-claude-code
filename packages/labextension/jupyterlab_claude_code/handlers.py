"""WebSocket and REST handlers for Claude Code integration."""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any, ClassVar

from jupyter_server.base.handlers import APIHandler, JupyterHandler
from jupyter_server.utils import url_path_join
from tornado import web
from tornado.websocket import WebSocketHandler

if TYPE_CHECKING:
    from tornado.web import Application

logger = logging.getLogger(__name__)


class ClaudeCodeWebSocketHandler(WebSocketHandler, JupyterHandler):
    """WebSocket handler for MCP server communication."""

    clients: ClassVar[set[ClaudeCodeWebSocketHandler]] = set()

    def check_origin(self, origin: str) -> bool:
        """Allow connections from localhost only."""
        return origin.startswith(("http://localhost", "http://127.0.0.1"))

    def open(self) -> None:
        """Handle new WebSocket connection."""
        ClaudeCodeWebSocketHandler.clients.add(self)
        logger.info("Claude Code MCP client connected")
        self.write_message(json.dumps({"type": "connected", "status": "ok"}))

    async def on_message(self, message: str | bytes) -> None:
        """Handle incoming messages from MCP server."""
        try:
            data = json.loads(message)
            await self._handle_request(data)
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
        except Exception as e:
            logger.exception("Error handling message")
            self._send_error(str(e))

    async def _handle_request(self, data: dict[str, Any]) -> None:
        """Route requests to appropriate handlers."""
        request_id = data.get("id", str(uuid.uuid4()))
        action = data.get("action")

        if not action:
            self._send_error("Missing action", request_id)
            return

        # Import here to avoid circular imports
        from .yjs_bridge import YjsBridge

        bridge = YjsBridge(self.settings)

        handlers = {
            # Notebook discovery
            "list_notebooks": bridge.list_notebooks,
            "get_active_notebook": bridge.get_active_notebook,
            "get_notebook_content": bridge.get_notebook_content,
            # Cell operations
            "get_cell": bridge.get_cell,
            "insert_cell": bridge.insert_cell,
            "update_cell": bridge.update_cell,
            "delete_cell": bridge.delete_cell,
            "move_cell": bridge.move_cell,
            # Kernel operations
            "execute_cell": bridge.execute_cell,
            "execute_code": bridge.execute_code,
            "interrupt_kernel": bridge.interrupt_kernel,
            "get_kernel_status": bridge.get_kernel_status,
            "list_variables": bridge.list_variables,
            # Output operations
            "get_cell_outputs": bridge.get_cell_outputs,
            "clear_outputs": bridge.clear_outputs,
        }

        handler = handlers.get(action)
        if not handler:
            self._send_error(f"Unknown action: {action}", request_id)
            return

        try:
            result = await handler(data.get("params", {}), data.get("notebook_id"))
            self._send_response(request_id, result)
        except Exception as e:
            logger.exception(f"Error executing {action}")
            self._send_error(str(e), request_id)

    def _send_response(self, request_id: str, data: Any) -> None:
        """Send successful response."""
        self.write_message(
            json.dumps({"id": request_id, "type": "response", "success": True, "data": data})
        )

    def _send_error(self, message: str, request_id: str | None = None) -> None:
        """Send error response."""
        self.write_message(
            json.dumps(
                {
                    "id": request_id,
                    "type": "response",
                    "success": False,
                    "error": message,
                }
            )
        )

    def on_close(self) -> None:
        """Handle WebSocket connection close."""
        ClaudeCodeWebSocketHandler.clients.discard(self)
        logger.info("Claude Code MCP client disconnected")


class StatusHandler(APIHandler):
    """REST endpoint for connection status."""

    @web.authenticated
    def get(self) -> None:
        """Return connection status."""
        self.finish(
            json.dumps(
                {
                    "status": "ok",
                    "connected_clients": len(ClaudeCodeWebSocketHandler.clients),
                }
            )
        )


def setup_handlers(web_app: Application) -> None:
    """Register handlers with the Jupyter server."""
    host_pattern = ".*$"
    base_url = web_app.settings["base_url"]

    handlers = [
        (url_path_join(base_url, "claude-code", "ws"), ClaudeCodeWebSocketHandler),
        (url_path_join(base_url, "claude-code", "status"), StatusHandler),
    ]

    web_app.add_handlers(host_pattern, handlers)
    logger.info("Claude Code handlers registered")
