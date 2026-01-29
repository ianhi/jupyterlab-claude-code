"""Bridge between WebSocket handlers and Yjs documents."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class YjsBridge:
    """Bridge for accessing and modifying Jupyter notebooks via Yjs."""

    def __init__(self, settings: dict[str, Any]) -> None:
        """Initialize the Yjs bridge.

        Args:
            settings: Tornado application settings containing Jupyter services.
        """
        self.settings = settings
        self._collaboration_manager = settings.get("jupyter_collaboration")
        self._contents_manager = settings.get("contents_manager")
        self._kernel_manager = settings.get("kernel_manager")
        self._session_manager = settings.get("session_manager")

    # -------------------------------------------------------------------------
    # Notebook Discovery
    # -------------------------------------------------------------------------

    def list_notebooks(
        self, _params: dict[str, Any], _notebook_id: str | None = None
    ) -> dict[str, Any]:
        """List all open notebooks in JupyterLab.

        Returns a list of notebook paths and their kernel status.
        """
        del _params, _notebook_id  # Unused but required by handler interface
        notebooks = []

        if self._session_manager:
            # Get sessions which represent open notebooks with kernels
            try:
                loop = asyncio.new_event_loop()
                sessions = loop.run_until_complete(self._session_manager.list_sessions())
                loop.close()

                for session in sessions:
                    if session.get("type") == "notebook":
                        notebooks.append(
                            {
                                "path": session.get("path"),
                                "name": session.get("name"),
                                "kernel_id": session.get("kernel", {}).get("id"),
                                "kernel_name": session.get("kernel", {}).get("name"),
                            }
                        )
            except Exception as e:
                logger.warning(f"Could not list sessions: {e}")

        return {"notebooks": notebooks}

    def get_active_notebook(
        self, params: dict[str, Any], notebook_id: str | None = None
    ) -> dict[str, Any]:
        """Get the currently active/focused notebook.

        Note: The active notebook is tracked by the frontend extension
        and communicated via a separate mechanism. For now, returns
        the first notebook if available.
        """
        result = self.list_notebooks(params, notebook_id)
        notebooks = result.get("notebooks", [])

        if notebooks:
            # Return first notebook as active (frontend will override)
            return {"notebook": notebooks[0], "is_fallback": True}
        return {"notebook": None, "is_fallback": False}

    def get_notebook_content(
        self, params: dict[str, Any], notebook_id: str | None = None
    ) -> dict[str, Any]:
        """Get full content of a notebook.

        Args:
            params: May contain 'path' to specify notebook.
            notebook_id: Notebook path/identifier.

        Returns:
            Notebook cells with their content and outputs.
        """
        path = notebook_id or params.get("path")
        if not path:
            raise ValueError("Notebook path required")

        if self._contents_manager:
            try:
                loop = asyncio.new_event_loop()
                model = loop.run_until_complete(
                    asyncio.to_thread(self._contents_manager.get, path, content=True)
                )
                loop.close()

                content = model.get("content", {})
                cells = content.get("cells", [])

                return {
                    "path": path,
                    "cells": [
                        {
                            "index": i,
                            "cell_type": cell.get("cell_type"),
                            "source": cell.get("source"),
                            "outputs": cell.get("outputs", []),
                            "metadata": cell.get("metadata", {}),
                        }
                        for i, cell in enumerate(cells)
                    ],
                    "metadata": content.get("metadata", {}),
                }
            except Exception as e:
                logger.exception(f"Error getting notebook content: {e}")
                raise

        raise RuntimeError("Contents manager not available")

    # -------------------------------------------------------------------------
    # Cell Operations
    # -------------------------------------------------------------------------

    def get_cell(self, params: dict[str, Any], notebook_id: str | None = None) -> dict[str, Any]:
        """Get content of a specific cell by index.

        Args:
            params: Must contain 'cell_index'.
            notebook_id: Notebook path.
        """
        cell_index = params.get("cell_index")
        if cell_index is None:
            raise ValueError("cell_index required")

        content = self.get_notebook_content(params, notebook_id)
        cells = content.get("cells", [])

        if cell_index < 0 or cell_index >= len(cells):
            raise IndexError(f"Cell index {cell_index} out of range (0-{len(cells) - 1})")

        return {"cell": cells[cell_index]}

    def insert_cell(self, params: dict[str, Any], notebook_id: str | None = None) -> dict[str, Any]:
        """Insert a new cell at the specified position.

        Args:
            params: Must contain 'cell_index', 'cell_type' (code/markdown),
                   and 'source'.
            notebook_id: Notebook path.
        """
        path = notebook_id or params.get("path")
        cell_index = params.get("cell_index")
        cell_type = params.get("cell_type", "code")
        source = params.get("source", "")

        if path is None:
            raise ValueError("Notebook path required")
        if cell_index is None:
            raise ValueError("cell_index required")

        return self._modify_notebook(
            path,
            "insert",
            cell_index=cell_index,
            cell_type=cell_type,
            source=source,
        )

    def update_cell(self, params: dict[str, Any], notebook_id: str | None = None) -> dict[str, Any]:
        """Update the source of an existing cell.

        Args:
            params: Must contain 'cell_index' and 'source'.
            notebook_id: Notebook path.
        """
        path = notebook_id or params.get("path")
        cell_index = params.get("cell_index")
        source = params.get("source")

        if path is None:
            raise ValueError("Notebook path required")
        if cell_index is None:
            raise ValueError("cell_index required")
        if source is None:
            raise ValueError("source required")

        return self._modify_notebook(path, "update", cell_index=cell_index, source=source)

    def delete_cell(self, params: dict[str, Any], notebook_id: str | None = None) -> dict[str, Any]:
        """Delete a cell by index.

        Args:
            params: Must contain 'cell_index'.
            notebook_id: Notebook path.
        """
        path = notebook_id or params.get("path")
        cell_index = params.get("cell_index")

        if path is None:
            raise ValueError("Notebook path required")
        if cell_index is None:
            raise ValueError("cell_index required")

        return self._modify_notebook(path, "delete", cell_index=cell_index)

    def move_cell(self, params: dict[str, Any], notebook_id: str | None = None) -> dict[str, Any]:
        """Move a cell to a new position.

        Args:
            params: Must contain 'from_index' and 'to_index'.
            notebook_id: Notebook path.
        """
        path = notebook_id or params.get("path")
        from_index = params.get("from_index")
        to_index = params.get("to_index")

        if path is None:
            raise ValueError("Notebook path required")
        if from_index is None or to_index is None:
            raise ValueError("from_index and to_index required")

        return self._modify_notebook(path, "move", from_index=from_index, to_index=to_index)

    def _modify_notebook(self, path: str, operation: str, **kwargs: Any) -> dict[str, Any]:
        """Modify a notebook's cells.

        This method handles the actual file modification.
        In the future, this will use Yjs for real-time sync.
        """
        if not self._contents_manager:
            raise RuntimeError("Contents manager not available")

        loop = asyncio.new_event_loop()

        try:
            # Get current content
            model = loop.run_until_complete(
                asyncio.to_thread(self._contents_manager.get, path, content=True)
            )
            content = model.get("content", {})
            cells = content.get("cells", [])

            # Perform operation
            if operation == "insert":
                new_cell = {
                    "cell_type": kwargs["cell_type"],
                    "source": kwargs["source"],
                    "metadata": {},
                }
                if kwargs["cell_type"] == "code":
                    new_cell["outputs"] = []
                    new_cell["execution_count"] = None
                cells.insert(kwargs["cell_index"], new_cell)

            elif operation == "update":
                idx = kwargs["cell_index"]
                if idx < 0 or idx >= len(cells):
                    raise IndexError(f"Cell index {idx} out of range")
                cells[idx]["source"] = kwargs["source"]

            elif operation == "delete":
                idx = kwargs["cell_index"]
                if idx < 0 or idx >= len(cells):
                    raise IndexError(f"Cell index {idx} out of range")
                del cells[idx]

            elif operation == "move":
                from_idx = kwargs["from_index"]
                to_idx = kwargs["to_index"]
                if from_idx < 0 or from_idx >= len(cells):
                    raise IndexError(f"from_index {from_idx} out of range")
                if to_idx < 0 or to_idx > len(cells):
                    raise IndexError(f"to_index {to_idx} out of range")
                cell = cells.pop(from_idx)
                cells.insert(to_idx, cell)

            # Save modified content
            content["cells"] = cells
            loop.run_until_complete(
                asyncio.to_thread(
                    self._contents_manager.save,
                    {"content": content, "type": "notebook"},
                    path,
                )
            )

            return {"success": True, "operation": operation, "cell_count": len(cells)}

        finally:
            loop.close()

    # -------------------------------------------------------------------------
    # Kernel Operations
    # -------------------------------------------------------------------------

    def execute_cell(
        self, params: dict[str, Any], notebook_id: str | None = None
    ) -> dict[str, Any]:
        """Execute a cell and return outputs.

        Args:
            params: Must contain 'cell_index'. Optional 'stream' for streaming.
            notebook_id: Notebook path.
        """
        path = notebook_id or params.get("path")
        cell_index = params.get("cell_index")

        if path is None:
            raise ValueError("Notebook path required")
        if cell_index is None:
            raise ValueError("cell_index required")

        # Get cell content
        cell_data = self.get_cell(params, path)
        source = cell_data["cell"]["source"]

        # Execute the code
        return self.execute_code({"code": source, "path": path}, path)

    def execute_code(
        self, params: dict[str, Any], notebook_id: str | None = None
    ) -> dict[str, Any]:
        """Execute arbitrary code in the kernel.

        Args:
            params: Must contain 'code'. Optional 'path' for kernel selection.
            notebook_id: Notebook path to determine which kernel to use.
        """
        code = params.get("code")
        path = notebook_id or params.get("path")

        if code is None:
            raise ValueError("code required")

        if not self._session_manager or not self._kernel_manager:
            raise RuntimeError("Kernel manager not available")

        loop = asyncio.new_event_loop()

        try:
            # Find kernel for this notebook
            sessions = loop.run_until_complete(self._session_manager.list_sessions())
            kernel_id = None

            for session in sessions:
                if session.get("path") == path:
                    kernel_id = session.get("kernel", {}).get("id")
                    break

            if not kernel_id:
                raise RuntimeError(f"No kernel found for notebook: {path}")

            # Get kernel and execute
            kernel = self._kernel_manager.get_kernel(kernel_id)
            client = kernel.client()

            # Execute and collect outputs
            msg_id = client.execute(code)
            outputs: list[dict[str, Any]] = []

            while True:
                try:
                    msg = client.get_iopub_msg(timeout=30)
                    msg_type = msg["header"]["msg_type"]

                    if msg["parent_header"].get("msg_id") != msg_id:
                        continue

                    if msg_type == "status" and msg["content"]["execution_state"] == "idle":
                        break
                    elif msg_type == "stream":
                        outputs.append(
                            {
                                "output_type": "stream",
                                "name": msg["content"]["name"],
                                "text": msg["content"]["text"],
                            }
                        )
                    elif msg_type in ("execute_result", "display_data"):
                        outputs.append(
                            {
                                "output_type": msg_type,
                                "data": msg["content"]["data"],
                                "metadata": msg["content"].get("metadata", {}),
                            }
                        )
                    elif msg_type == "error":
                        outputs.append(
                            {
                                "output_type": "error",
                                "ename": msg["content"]["ename"],
                                "evalue": msg["content"]["evalue"],
                                "traceback": msg["content"]["traceback"],
                            }
                        )

                except TimeoutError:
                    break

            return {"outputs": outputs, "success": True}

        finally:
            loop.close()

    def interrupt_kernel(
        self, params: dict[str, Any], notebook_id: str | None = None
    ) -> dict[str, Any]:
        """Interrupt current kernel execution.

        Args:
            params: Optional 'path' for kernel selection.
            notebook_id: Notebook path.
        """
        path = notebook_id or params.get("path")

        if not self._session_manager or not self._kernel_manager:
            raise RuntimeError("Kernel manager not available")

        loop = asyncio.new_event_loop()

        try:
            sessions = loop.run_until_complete(self._session_manager.list_sessions())

            for session in sessions:
                if session.get("path") == path:
                    kernel_id = session.get("kernel", {}).get("id")
                    if kernel_id:
                        loop.run_until_complete(
                            asyncio.to_thread(
                                self._kernel_manager.interrupt_kernel,
                                kernel_id,
                            )
                        )
                        return {"success": True, "kernel_id": kernel_id}

            raise RuntimeError(f"No kernel found for notebook: {path}")

        finally:
            loop.close()

    def get_kernel_status(
        self, params: dict[str, Any], notebook_id: str | None = None
    ) -> dict[str, Any]:
        """Check if kernel is idle/busy.

        Args:
            params: Optional 'path' for kernel selection.
            notebook_id: Notebook path.
        """
        path = notebook_id or params.get("path")

        if not self._session_manager or not self._kernel_manager:
            raise RuntimeError("Kernel manager not available")

        loop = asyncio.new_event_loop()

        try:
            sessions = loop.run_until_complete(self._session_manager.list_sessions())

            for session in sessions:
                if session.get("path") == path:
                    kernel_id = session.get("kernel", {}).get("id")
                    if kernel_id:
                        kernel = self._kernel_manager.get_kernel(kernel_id)
                        return {
                            "kernel_id": kernel_id,
                            "execution_state": kernel.execution_state,
                            "is_alive": kernel.is_alive(),
                        }

            raise RuntimeError(f"No kernel found for notebook: {path}")

        finally:
            loop.close()

    def list_variables(
        self, params: dict[str, Any], notebook_id: str | None = None
    ) -> dict[str, Any]:
        """Inspect variables in kernel namespace.

        Args:
            params: Optional 'path' for kernel selection.
            notebook_id: Notebook path.
        """
        # Execute code to get variable information
        inspect_code = """
import json
_vars = {}
for _name in dir():
    if not _name.startswith('_'):
        try:
            _obj = eval(_name)
            _vars[_name] = {
                'type': type(_obj).__name__,
                'repr': repr(_obj)[:100]
            }
        except Exception:
            pass
print(json.dumps(_vars))
"""
        result = self.execute_code(
            {"code": inspect_code, "path": notebook_id or params.get("path")}, notebook_id
        )

        # Parse the output
        outputs = result.get("outputs", [])
        for output in outputs:
            if output.get("output_type") == "stream" and output.get("name") == "stdout":
                import json

                try:
                    variables = json.loads(output["text"].strip())
                    return {"variables": variables}
                except json.JSONDecodeError:
                    pass

        return {"variables": {}}

    # -------------------------------------------------------------------------
    # Output Operations
    # -------------------------------------------------------------------------

    def get_cell_outputs(
        self, params: dict[str, Any], notebook_id: str | None = None
    ) -> dict[str, Any]:
        """Get outputs from a specific cell.

        Args:
            params: Must contain 'cell_index'.
            notebook_id: Notebook path.
        """
        cell_data = self.get_cell(params, notebook_id)
        cell = cell_data.get("cell", {})

        return {"outputs": cell.get("outputs", []), "cell_type": cell.get("cell_type")}

    def clear_outputs(
        self, params: dict[str, Any], notebook_id: str | None = None
    ) -> dict[str, Any]:
        """Clear outputs from a cell or all cells.

        Args:
            params: Optional 'cell_index' for specific cell, otherwise clears all.
            notebook_id: Notebook path.
        """
        path = notebook_id or params.get("path")
        cell_index = params.get("cell_index")

        if path is None:
            raise ValueError("Notebook path required")

        if not self._contents_manager:
            raise RuntimeError("Contents manager not available")

        loop = asyncio.new_event_loop()

        try:
            model = loop.run_until_complete(
                asyncio.to_thread(self._contents_manager.get, path, content=True)
            )
            content = model.get("content", {})
            cells = content.get("cells", [])

            if cell_index is not None:
                # Clear specific cell
                if cell_index < 0 or cell_index >= len(cells):
                    raise IndexError(f"Cell index {cell_index} out of range")
                if cells[cell_index].get("cell_type") == "code":
                    cells[cell_index]["outputs"] = []
                    cells[cell_index]["execution_count"] = None
            else:
                # Clear all cells
                for cell in cells:
                    if cell.get("cell_type") == "code":
                        cell["outputs"] = []
                        cell["execution_count"] = None

            content["cells"] = cells
            loop.run_until_complete(
                asyncio.to_thread(
                    self._contents_manager.save,
                    {"content": content, "type": "notebook"},
                    path,
                )
            )

            return {"success": True, "cleared": "all" if cell_index is None else cell_index}

        finally:
            loop.close()
