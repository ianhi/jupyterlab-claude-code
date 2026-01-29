"""MCP tools for cell manipulation in JupyterLab notebooks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server import Server

    from jupyterlab_claude_mcp.client import JupyterLabClient

logger = logging.getLogger(__name__)


def register_cell_tools(mcp_server: Server, client: JupyterLabClient) -> None:
    """Register cell manipulation tools with the MCP server.

    Args:
        mcp_server: The MCP server instance to register tools with.
        client: WebSocket client for communicating with JupyterLab.
    """

    @mcp_server.call_tool()
    async def get_cell(
        cell_index: int,
        notebook_path: str | None = None,
    ) -> dict[str, Any]:
        """Get the content of a specific cell by index.

        Retrieves the full content of a cell including its source code,
        cell type (code/markdown), outputs, and metadata.

        Args:
            cell_index: The 0-indexed position of the cell to retrieve.
            notebook_path: Path to the notebook. If not specified, uses the
                currently active notebook in JupyterLab.

        Returns:
            A dictionary containing the cell information:
            - index: The cell index
            - cell_type: Either "code" or "markdown"
            - source: The cell's source content
            - outputs: List of cell outputs (for code cells)
            - metadata: Cell metadata dictionary
        """
        if cell_index < 0:
            return {"error": f"cell_index must be non-negative, got {cell_index}"}

        params: dict[str, Any] = {"cell_index": cell_index}
        if notebook_path:
            params["path"] = notebook_path

        try:
            response = await client.send_request(
                "get_cell",
                notebook_id=notebook_path,
                params=params,
            )
            return response.data.get("cell", {})
        except Exception as e:
            logger.exception("Error getting cell")
            return {"error": str(e)}

    @mcp_server.call_tool()
    async def insert_cell(
        cell_index: int,
        source: str,
        cell_type: str = "code",
        notebook_path: str | None = None,
    ) -> dict[str, Any]:
        """Insert a new cell at the specified position.

        Creates a new cell with the given content and inserts it at the
        specified index. All cells at and after that index are shifted down.

        Args:
            cell_index: Position to insert the cell (0-indexed). The new cell
                will be inserted before the cell currently at this index.
                Use the total cell count to append at the end.
            source: The cell content/source code to insert.
            cell_type: Either "code" or "markdown". Defaults to "code".
            notebook_path: Path to the notebook. If not specified, uses the
                currently active notebook in JupyterLab.

        Returns:
            A dictionary with:
            - success: Boolean indicating if the operation succeeded
            - operation: "insert"
            - cell_count: Total number of cells after insertion
        """
        if cell_index < 0:
            return {"error": f"cell_index must be non-negative, got {cell_index}"}

        if cell_type not in ("code", "markdown"):
            return {"error": f"cell_type must be 'code' or 'markdown', got '{cell_type}'"}

        params: dict[str, Any] = {
            "cell_index": cell_index,
            "source": source,
            "cell_type": cell_type,
        }
        if notebook_path:
            params["path"] = notebook_path

        try:
            response = await client.send_request(
                "insert_cell",
                notebook_id=notebook_path,
                params=params,
            )
            return response.data
        except Exception as e:
            logger.exception("Error inserting cell")
            return {"error": str(e), "success": False}

    @mcp_server.call_tool()
    async def update_cell(
        cell_index: int,
        source: str,
        notebook_path: str | None = None,
    ) -> dict[str, Any]:
        """Update the source content of an existing cell.

        Replaces the source code/content of the cell at the specified index
        with new content. The cell type and metadata are preserved.

        Args:
            cell_index: The 0-indexed position of the cell to update.
            source: The new source content for the cell.
            notebook_path: Path to the notebook. If not specified, uses the
                currently active notebook in JupyterLab.

        Returns:
            A dictionary with:
            - success: Boolean indicating if the operation succeeded
            - operation: "update"
            - cell_count: Total number of cells in the notebook
        """
        if cell_index < 0:
            return {"error": f"cell_index must be non-negative, got {cell_index}"}

        params: dict[str, Any] = {
            "cell_index": cell_index,
            "source": source,
        }
        if notebook_path:
            params["path"] = notebook_path

        try:
            response = await client.send_request(
                "update_cell",
                notebook_id=notebook_path,
                params=params,
            )
            return response.data
        except Exception as e:
            logger.exception("Error updating cell")
            return {"error": str(e), "success": False}

    @mcp_server.call_tool()
    async def delete_cell(
        cell_index: int,
        notebook_path: str | None = None,
    ) -> dict[str, Any]:
        """Delete a cell by index.

        Removes the cell at the specified index from the notebook.
        All cells after the deleted cell are shifted up.

        Args:
            cell_index: The 0-indexed position of the cell to delete.
            notebook_path: Path to the notebook. If not specified, uses the
                currently active notebook in JupyterLab.

        Returns:
            A dictionary with:
            - success: Boolean indicating if the operation succeeded
            - operation: "delete"
            - cell_count: Total number of cells after deletion
        """
        if cell_index < 0:
            return {"error": f"cell_index must be non-negative, got {cell_index}"}

        params: dict[str, Any] = {"cell_index": cell_index}
        if notebook_path:
            params["path"] = notebook_path

        try:
            response = await client.send_request(
                "delete_cell",
                notebook_id=notebook_path,
                params=params,
            )
            return response.data
        except Exception as e:
            logger.exception("Error deleting cell")
            return {"error": str(e), "success": False}

    @mcp_server.call_tool()
    async def move_cell(
        from_index: int,
        to_index: int,
        notebook_path: str | None = None,
    ) -> dict[str, Any]:
        """Move a cell to a new position in the notebook.

        Relocates a cell from one position to another. The cell is removed
        from its original position and inserted at the target position.

        Args:
            from_index: The current 0-indexed position of the cell to move.
            to_index: The target 0-indexed position where the cell should
                be moved. After the operation, the cell will be at this index.
            notebook_path: Path to the notebook. If not specified, uses the
                currently active notebook in JupyterLab.

        Returns:
            A dictionary with:
            - success: Boolean indicating if the operation succeeded
            - operation: "move"
            - cell_count: Total number of cells in the notebook
        """
        if from_index < 0:
            return {"error": f"from_index must be non-negative, got {from_index}"}
        if to_index < 0:
            return {"error": f"to_index must be non-negative, got {to_index}"}

        params: dict[str, Any] = {
            "from_index": from_index,
            "to_index": to_index,
        }
        if notebook_path:
            params["path"] = notebook_path

        try:
            response = await client.send_request(
                "move_cell",
                notebook_id=notebook_path,
                params=params,
            )
            return response.data
        except Exception as e:
            logger.exception("Error moving cell")
            return {"error": str(e), "success": False}

    logger.info("Registered cell tools: get_cell, insert_cell, update_cell, delete_cell, move_cell")
