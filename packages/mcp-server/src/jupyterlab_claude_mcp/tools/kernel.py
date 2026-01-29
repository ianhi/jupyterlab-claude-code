"""MCP tools for kernel execution operations in JupyterLab."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server import Server

    from jupyterlab_claude_mcp.client import JupyterLabClient

logger = logging.getLogger(__name__)


def register_kernel_tools(mcp_server: Server, client: JupyterLabClient) -> None:
    """Register kernel execution MCP tools.

    Args:
        mcp_server: The MCP server instance to register tools with.
        client: The JupyterLab WebSocket client for communication.
    """

    @mcp_server.call_tool()
    async def execute_cell(
        cell_index: int,
        notebook_path: str | None = None,
    ) -> dict[str, Any]:
        """Execute a cell by index and return its outputs.

        Runs the code in the specified cell using the notebook's kernel
        and returns all outputs including stdout, stderr, execution results,
        display data, and errors.

        Args:
            cell_index: The zero-based index of the cell to execute.
            notebook_path: Path to the notebook. Uses active notebook if not specified.

        Returns:
            Dict containing:
                - outputs: List of output objects (stream, execute_result, display_data, error)
                - success: Whether execution completed without errors
        """
        params: dict[str, Any] = {"cell_index": cell_index}
        if notebook_path:
            params["path"] = notebook_path

        try:
            response = await client.send_request(
                "execute_cell",
                notebook_id=notebook_path,
                params=params,
            )
            return {
                "outputs": response.data.get("outputs", []),
                "success": response.data.get("success", True),
            }
        except Exception as e:
            logger.exception("Error executing cell")
            return {"outputs": [], "success": False, "error": str(e)}

    @mcp_server.call_tool()
    async def execute_code(
        code: str,
        notebook_path: str | None = None,
    ) -> dict[str, Any]:
        """Execute arbitrary Python code in the notebook's kernel.

        Runs the provided code string in the active kernel associated with
        the specified notebook and returns all outputs.

        Args:
            code: The Python code to execute.
            notebook_path: Path to notebook (uses active notebook if not specified).

        Returns:
            Dict containing:
                - outputs: List of output objects from execution
                - success: Whether execution completed without errors
        """
        params: dict[str, Any] = {"code": code}
        if notebook_path:
            params["path"] = notebook_path

        try:
            response = await client.send_request(
                "execute_code",
                notebook_id=notebook_path,
                params=params,
            )
            return {
                "outputs": response.data.get("outputs", []),
                "success": response.data.get("success", True),
            }
        except Exception as e:
            logger.exception("Error executing code")
            return {"outputs": [], "success": False, "error": str(e)}

    @mcp_server.call_tool()
    async def interrupt_kernel(notebook_path: str | None = None) -> dict[str, Any]:
        """Interrupt the currently running kernel execution.

        Sends an interrupt signal to the kernel, stopping any code that is
        currently running. This is equivalent to pressing Ctrl+C in a terminal.

        Args:
            notebook_path: Path to the notebook whose kernel should be interrupted.
                          Uses active notebook if not specified.

        Returns:
            Dict containing:
                - success: Whether the interrupt was sent successfully
                - kernel_id: The ID of the interrupted kernel
        """
        params: dict[str, Any] = {}
        if notebook_path:
            params["path"] = notebook_path

        try:
            response = await client.send_request(
                "interrupt_kernel",
                notebook_id=notebook_path,
                params=params,
            )
            return {
                "success": response.data.get("success", True),
                "kernel_id": response.data.get("kernel_id"),
            }
        except Exception as e:
            logger.exception("Error interrupting kernel")
            return {"success": False, "error": str(e)}

    @mcp_server.call_tool()
    async def get_kernel_status(notebook_path: str | None = None) -> dict[str, Any]:
        """Check if the kernel is idle, busy, or in another state.

        Returns the current execution state of the kernel and whether it is alive.

        Args:
            notebook_path: Path to the notebook to check. Uses active notebook if not specified.

        Returns:
            Dict containing:
                - kernel_id: The kernel's unique identifier
                - execution_state: Current state ("idle", "busy", "starting", etc.)
                - is_alive: Whether the kernel process is running
        """
        params: dict[str, Any] = {}
        if notebook_path:
            params["path"] = notebook_path

        try:
            response = await client.send_request(
                "get_kernel_status",
                notebook_id=notebook_path,
                params=params,
            )
            return {
                "kernel_id": response.data.get("kernel_id"),
                "execution_state": response.data.get("execution_state", "unknown"),
                "is_alive": response.data.get("is_alive", False),
            }
        except Exception as e:
            logger.exception("Error getting kernel status")
            return {
                "kernel_id": None,
                "execution_state": "unknown",
                "is_alive": False,
                "error": str(e),
            }

    @mcp_server.call_tool()
    async def list_variables(notebook_path: str | None = None) -> dict[str, Any]:
        """Inspect variables in the kernel's namespace.

        Retrieves information about all user-defined variables currently
        in the kernel's namespace, including their types and string representations.

        Args:
            notebook_path: Path to the notebook. Uses active notebook if not specified.

        Returns:
            Dict containing:
                - variables: Dict mapping variable names to their info:
                    - type: The Python type name (e.g., "int", "DataFrame")
                    - repr: String representation (truncated to 100 chars)
        """
        params: dict[str, Any] = {}
        if notebook_path:
            params["path"] = notebook_path

        try:
            response = await client.send_request(
                "list_variables",
                notebook_id=notebook_path,
                params=params,
            )
            return {"variables": response.data.get("variables", {})}
        except Exception as e:
            logger.exception("Error listing variables")
            return {"variables": {}, "error": str(e)}

    @mcp_server.call_tool()
    async def get_cell_outputs(
        cell_index: int,
        notebook_path: str | None = None,
    ) -> dict[str, Any]:
        """Get the outputs from a specific cell.

        Retrieves all stored outputs from a cell, including text output,
        images, HTML, errors, and other rich display data.

        Args:
            cell_index: The zero-based index of the cell.
            notebook_path: Path to the notebook. Uses active notebook if not specified.

        Returns:
            Dict containing:
                - outputs: List of output objects stored in the cell
                - cell_type: The type of cell ("code" or "markdown")
        """
        params: dict[str, Any] = {"cell_index": cell_index}
        if notebook_path:
            params["path"] = notebook_path

        try:
            response = await client.send_request(
                "get_cell_outputs",
                notebook_id=notebook_path,
                params=params,
            )
            return {
                "outputs": response.data.get("outputs", []),
                "cell_type": response.data.get("cell_type", "unknown"),
            }
        except Exception as e:
            logger.exception("Error getting cell outputs")
            return {"outputs": [], "cell_type": "unknown", "error": str(e)}

    @mcp_server.call_tool()
    async def clear_outputs(
        cell_index: int | None = None,
        notebook_path: str | None = None,
    ) -> dict[str, Any]:
        """Clear outputs from a cell or all cells in a notebook.

        Removes all outputs and resets execution counts. If a cell_index is
        provided, only that cell's outputs are cleared. Otherwise, all cells
        in the notebook have their outputs cleared.

        Args:
            cell_index: The zero-based index of a specific cell to clear.
                       If None, clears outputs from all cells.
            notebook_path: Path to the notebook. Uses active notebook if not specified.

        Returns:
            Dict containing:
                - success: Whether the operation completed successfully
                - cleared: Either "all" or the specific cell index that was cleared
        """
        params: dict[str, Any] = {}
        if cell_index is not None:
            params["cell_index"] = cell_index
        if notebook_path:
            params["path"] = notebook_path

        try:
            response = await client.send_request(
                "clear_outputs",
                notebook_id=notebook_path,
                params=params,
            )
            return {
                "success": response.data.get("success", True),
                "cleared": response.data.get("cleared"),
            }
        except Exception as e:
            logger.exception("Error clearing outputs")
            return {"success": False, "error": str(e)}

    logger.info(
        "Registered kernel tools: execute_cell, execute_code, interrupt_kernel, "
        "get_kernel_status, list_variables, get_cell_outputs, clear_outputs"
    )
