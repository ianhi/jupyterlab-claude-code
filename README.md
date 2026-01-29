# JupyterLab + Claude Code Integration

A seamless integration allowing Claude Code to interact with JupyterLab notebooks in real-time via MCP (Model Context Protocol).

## Features

- **Real-time collaboration**: See Claude's changes appear instantly in your notebook (like Google Docs)
- **Kernel execution**: Claude can execute code in your active kernel and see results
- **Cell manipulation**: Insert, modify, and delete cells programmatically
- **No save/revert workflow**: Changes sync automatically via Yjs CRDT

## Architecture

```
┌─────────────────┐         stdio          ┌─────────────────────┐
│   Claude Code   │◄─────────────────────►│    MCP Server       │
│                 │      (JSON-RPC)        │    (Python)         │
└─────────────────┘                        └──────────┬──────────┘
                                                      │
                                                      │ WebSocket
                                                      │ (Yjs + Custom)
                                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    JupyterLab Server                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           Server Extension (Python)                      │   │
│  │  - WebSocket endpoint for MCP server                     │   │
│  │  - Yjs document provider (notebook sync)                 │   │
│  │  - Kernel execution proxy                                │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.10+
- JupyterLab 4.x
- jupyter-collaboration (for Yjs real-time sync)
- uv (Python package manager)
- npm (for building the frontend extension)

### Install from source

```bash
# Clone the repository
git clone https://github.com/yourusername/jupyterlab-claude-code.git
cd jupyterlab-claude-code

# Install all packages in development mode
uv sync

# Build the frontend extension
npm install
npm run build

# Install the JupyterLab extension
uv run jupyter labextension develop packages/labextension --overwrite
```

## Configuration

### Configure Claude Code to use the MCP server

Add to your Claude Code MCP configuration (`~/.claude/mcp.json`):

```json
{
  "mcpServers": {
    "jupyterlab": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/jupyterlab-claude-code", "jupyterlab-claude-mcp"],
      "env": {
        "JUPYTER_TOKEN": "your-jupyter-token",
        "JUPYTER_URL": "http://localhost:8888"
      }
    }
  }
}
```

### Get your Jupyter token

```bash
jupyter server list
```

## Usage

1. Start JupyterLab: `jupyter lab`
2. Open a notebook
3. In Claude Code, use commands like:
   - "What notebooks are open in JupyterLab?"
   - "Show me the contents of the active notebook"
   - "Add a cell that imports pandas"
   - "Execute the first cell and show me the output"

## MCP Tools

### Notebook Discovery
- `list_notebooks` - List all open notebooks
- `get_active_notebook` - Get the currently focused notebook
- `get_notebook_content` - Get full notebook content

### Cell Operations
- `get_cell` - Get content of a specific cell
- `insert_cell` - Insert a new cell
- `update_cell` - Update cell source
- `delete_cell` - Delete a cell
- `move_cell` - Move a cell to new position

### Kernel Execution
- `execute_cell` - Execute a cell and return outputs
- `execute_code` - Execute arbitrary code
- `interrupt_kernel` - Interrupt execution
- `get_kernel_status` - Check kernel status
- `list_variables` - Inspect kernel namespace

### Outputs
- `get_cell_outputs` - Get cell outputs
- `clear_outputs` - Clear outputs

## Development

```bash
# Watch for changes (frontend)
npm run watch

# Run MCP server directly for testing
uv run jupyterlab-claude-mcp

# Run tests
uv run pytest
```

## License

MIT
