"""JupyterLab extension for Claude Code integration."""

from .handlers import setup_handlers


def _jupyter_labextension_paths():
    return [{"src": "labextension", "dest": "@jupyterlab-claude-code/labextension"}]


def _jupyter_server_extension_points():
    return [{"module": "jupyterlab_claude_code"}]


def _load_jupyter_server_extension(server_app):
    """Register the API handler to receive HTTP requests from the frontend."""
    setup_handlers(server_app.web_app)
    name = "jupyterlab_claude_code"
    server_app.log.info(f"Registered {name} server extension")


# For backward compatibility
load_jupyter_server_extension = _load_jupyter_server_extension
