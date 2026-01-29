import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin,
} from "@jupyterlab/application";
import { INotebookTracker } from "@jupyterlab/notebook";
import { IStatusBar } from "@jupyterlab/statusbar";
import { Widget } from "@lumino/widgets";

/**
 * Status widget showing Claude Code connection status
 */
class ClaudeCodeStatus extends Widget {
  private _statusElement: HTMLSpanElement;
  private _connected: boolean = false;

  constructor() {
    super();
    this.addClass("jp-ClaudeCodeStatus");

    const container = document.createElement("div");
    container.className = "jp-ClaudeCodeStatus-container";

    const icon = document.createElement("span");
    icon.className = "jp-ClaudeCodeStatus-icon";
    icon.innerHTML = "⬤";

    this._statusElement = document.createElement("span");
    this._statusElement.className = "jp-ClaudeCodeStatus-text";
    this._statusElement.textContent = "Claude";

    container.appendChild(icon);
    container.appendChild(this._statusElement);
    this.node.appendChild(container);

    this.setConnected(false);
  }

  setConnected(connected: boolean): void {
    this._connected = connected;
    const icon = this.node.querySelector(
      ".jp-ClaudeCodeStatus-icon"
    ) as HTMLElement;
    if (icon) {
      icon.style.color = connected ? "#10b981" : "#6b7280";
    }
    this._statusElement.textContent = connected
      ? "Claude Connected"
      : "Claude";
    this.node.title = connected
      ? "Claude Code MCP server is connected"
      : "Claude Code MCP server is not connected";
  }

  get connected(): boolean {
    return this._connected;
  }
}

/**
 * Track the currently active notebook for the MCP server
 */
class NotebookActivityTracker {
  private _tracker: INotebookTracker;
  private _activeNotebook: string | null = null;

  constructor(tracker: INotebookTracker) {
    this._tracker = tracker;

    // Track active notebook changes
    this._tracker.currentChanged.connect((_sender, widget) => {
      if (widget) {
        this._activeNotebook = widget.context.path;
        this._notifyActiveNotebook();
      } else {
        this._activeNotebook = null;
      }
    });
  }

  get activeNotebook(): string | null {
    return this._activeNotebook;
  }

  private _notifyActiveNotebook(): void {
    // Send active notebook to server extension
    // This will be used by the MCP server to determine which notebook to operate on
    if (this._activeNotebook) {
      fetch("/claude-code/active-notebook", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ path: this._activeNotebook }),
      }).catch(() => {
        // Silently fail - server may not be ready
      });
    }
  }
}

/**
 * Poll for connection status from the server extension
 */
async function checkConnectionStatus(
  statusWidget: ClaudeCodeStatus
): Promise<void> {
  try {
    const response = await fetch("/claude-code/status");
    if (response.ok) {
      const data = await response.json();
      statusWidget.setConnected(data.connected_clients > 0);
    } else {
      statusWidget.setConnected(false);
    }
  } catch {
    statusWidget.setConnected(false);
  }
}

/**
 * The main plugin for Claude Code integration
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: "@jupyterlab-claude-code/labextension:plugin",
  description: "JupyterLab extension for Claude Code integration",
  autoStart: true,
  requires: [INotebookTracker],
  optional: [IStatusBar],
  activate: (
    app: JupyterFrontEnd,
    notebookTracker: INotebookTracker,
    statusBar: IStatusBar | null
  ) => {
    console.log("Claude Code extension activated");

    // Create notebook activity tracker
    new NotebookActivityTracker(notebookTracker);

    // Add status bar widget if available
    if (statusBar) {
      const statusWidget = new ClaudeCodeStatus();

      statusBar.registerStatusItem(
        "@jupyterlab-claude-code/labextension:status",
        {
          item: statusWidget,
          align: "right",
          rank: 100,
        }
      );

      // Poll for connection status every 5 seconds
      checkConnectionStatus(statusWidget);
      setInterval(() => checkConnectionStatus(statusWidget), 5000);
    }
  },
};

export default plugin;
