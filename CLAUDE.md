# JupyterLab + Claude Code Integration

## Project Overview

This monorepo contains an MCP server and JupyterLab extension that enables Claude Code to interact with JupyterLab notebooks in real-time.

## Structure

```
packages/
├── mcp-server/          # MCP Server (Python) - connects to Claude Code via stdio
└── labextension/        # JupyterLab Extension (Python server + TypeScript frontend)
```

## Key Technologies

- **Python**: uv for package management, FastMCP for MCP server
- **TypeScript**: JupyterLab 4.x extension API
- **Real-time sync**: Yjs CRDT via jupyter-collaboration
- **Communication**: WebSocket between MCP server and JupyterLab server extension

## Development Commands

```bash
# Install dependencies
uv sync
npm install

# Build frontend
npm run build

# Watch mode for frontend development
npm run watch

# Run MCP server directly
uv run jupyterlab-claude-mcp

# Install extension in development mode
uv run jupyter labextension develop packages/labextension --overwrite
```

## Testing

```bash
# Start JupyterLab
jupyter lab --port=8888

# In another terminal, test MCP server
uv run jupyterlab-claude-mcp
```

## Architecture Notes

1. **MCP Server** (`packages/mcp-server`):
   - Runs as stdio process spawned by Claude Code
   - Connects to JupyterLab via WebSocket
   - Exposes MCP tools for notebook manipulation

2. **JupyterLab Extension** (`packages/labextension`):
   - Server extension: WebSocket endpoint, Yjs bridge, kernel proxy
   - Frontend extension: Connection status UI

3. **Real-time Collaboration**:
   - Uses jupyter-collaboration's Yjs infrastructure
   - Changes made via MCP appear instantly in user's notebook
   - No manual save/revert needed

## Environment Variables

- `JUPYTER_URL`: JupyterLab server URL (default: http://localhost:8888)
- `JUPYTER_TOKEN`: Authentication token for JupyterLab
