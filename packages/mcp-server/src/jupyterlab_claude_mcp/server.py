"""MCP server for JupyterLab integration with Claude Code."""

from __future__ import annotations

import asyncio
import logging
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server

from .client import JupyterLabClient, close_client, get_client
from .tools import register_cell_tools, register_kernel_tools, register_notebook_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def create_server() -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("jupyterlab-claude-mcp")

    # We'll register tools once the client is connected
    return server


async def run_server() -> None:
    """Run the MCP server."""
    server = create_server()

    # Connect to JupyterLab
    logger.info("Connecting to JupyterLab...")
    try:
        client = await get_client()
        logger.info("Connected to JupyterLab successfully")
    except Exception as e:
        logger.error(f"Failed to connect to JupyterLab: {e}")
        logger.info("Server will start but tools may not work until JupyterLab is available")
        client = JupyterLabClient()  # Create unconnected client

    # Register all tools
    register_notebook_tools(server, client)
    register_cell_tools(server, client)
    register_kernel_tools(server, client)

    logger.info("MCP server starting...")

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        await close_client()
        logger.info("MCP server stopped")


def main() -> None:
    """Entry point for the MCP server."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.exception(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
