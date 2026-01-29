# Testing Guide

## Quick Start

### 1. Install the packages

```bash
cd /Users/ian/Documents/dev/jupyterlab-claude-code

# Install both packages
uv pip install -e packages/labextension -e packages/mcp-server
```

### 2. Start JupyterLab

```bash
uv run jupyter lab --port=8888
```

You should see in the logs:
```
Claude Code connection file written: ~/.jupyter/claude-code-connections/abc123.json
  Instance ID: abc123
  Port: 8888
```

### 3. Configure Claude Code MCP

Create or edit `.mcp.json` in your project directory:

```json
{
  "mcpServers": {
    "jupyterlab": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/ian/Documents/dev/jupyterlab-claude-code", "jupyterlab-claude-mcp"]
    }
  }
}
```

Note: No token needed! The MCP server auto-discovers running JupyterLab instances.

### 4. Restart Claude Code

Exit and restart Claude Code so it loads the new MCP config.

### 5. Test

Try these commands:
- "List available JupyterLab instances"
- "List the notebooks open in JupyterLab"
- "Show me the content of notebook X"

## Troubleshooting

### "No JupyterLab instances found"

1. Make sure JupyterLab is running with the extension installed
2. Check that `~/.jupyter/claude-code-connections/` has a `.json` file
3. The extension may not be loading - check JupyterLab logs

### Multiple instances

If you have multiple JupyterLab servers running:

```json
{
  "mcpServers": {
    "jupyterlab": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/ian/Documents/dev/jupyterlab-claude-code", "jupyterlab-claude-mcp"],
      "env": {
        "JUPYTER_INSTANCE_ID": "abc123"
      }
    }
  }
}
```

Or specify the port:

```json
{
  "env": {
    "JUPYTER_PORT": "8889"
  }
}
```

## Manual Testing (without Claude Code)

Test the MCP server directly:

```bash
# Terminal 1: Start JupyterLab
uv run jupyter lab --port=8888

# Terminal 2: Test MCP server connection
uv run jupyterlab-claude-mcp
```

The MCP server should log that it connected to JupyterLab.
