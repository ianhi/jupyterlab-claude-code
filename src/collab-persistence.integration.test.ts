/**
 * TRUE integration test for collaboration persistence integrity, against a REAL
 * jupyter-collaboration server (spawned via `uv run jupyter server`). Unlike the
 * fake-socket integration tests, this drives the actual RTC handshake, the live
 * Yjs room, the forced-save control message, and the Contents API round-trip —
 * the exact machinery the collab-desync bug reports lived in.
 *
 * Regression guard for the fix that made `getNotebookConnection` refuse to hand
 * back a desynced connection and `save_notebook` verify persistence before
 * reporting success. Case B is red on the pre-fix code (a desynced edit is
 * reported "verified" while disk stays stale) and green after.
 *
 * The suite self-skips if a real server can't be launched (e.g. no `uv` /
 * jupyter-collaboration in CI) rather than hanging.
 */
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { spawn, type ChildProcess } from "node:child_process";
import { createServer } from "node:net";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  setJupyterConfig,
  checkRtcAvailability,
  getNotebookConnection,
  connectedNotebooks,
  evictNotebook,
  type JupyterConfig,
} from "./connection.js";
import { handlers as cellWriteHandlers } from "./handlers/cell-write.js";
import { handlers as connectionHandlers } from "./handlers/connection.js";

const NB_PATH = "nb.ipynb";

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = createServer();
    srv.on("error", reject);
    srv.listen(0, () => {
      const addr = srv.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      srv.close(() => resolve(port));
    });
  });
}

async function waitForStatus(baseUrl: string, token: string, tries = 60): Promise<boolean> {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(`${baseUrl}/api/status`, {
        headers: { Authorization: `token ${token}` },
      });
      if (res.ok) return true;
    } catch {
      /* server not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

const MINIMAL_NB = JSON.stringify({
  cells: [
    {
      cell_type: "code",
      source: "# original",
      metadata: {},
      outputs: [],
      execution_count: null,
      id: "cell-one",
    },
  ],
  metadata: {},
  nbformat: 4,
  nbformat_minor: 5,
});

/** Read the on-disk .ipynb and return the joined source of all cells. */
async function diskSources(rootDir: string): Promise<string> {
  const raw = await readFile(join(rootDir, NB_PATH), "utf8");
  const nb = JSON.parse(raw);
  return (nb.cells ?? [])
    .map((c: any) => (Array.isArray(c.source) ? c.source.join("") : c.source))
    .join("\n---\n");
}

function textOf(result: { content: { type: string; text?: string }[] }): string {
  return result.content.map((c) => c.text ?? "").join("");
}

let server: ChildProcess | undefined;
let rootDir = "";
let ready = false;

beforeAll(async () => {
  rootDir = await mkdtemp(join(tmpdir(), "collab-int-"));
  await writeFile(join(rootDir, NB_PATH), MINIMAL_NB);

  const port = await freePort();
  const token = "int-test-token";
  const baseUrl = `http://localhost:${port}`;

  server = spawn(
    "uv",
    [
      "run",
      "--with",
      "jupyterlab",
      "--with",
      "jupyter-collaboration",
      "jupyter",
      "server",
      `--ServerApp.port=${port}`,
      `--IdentityProvider.token=${token}`,
      `--ServerApp.root_dir=${rootDir}`,
      "--no-browser",
      "--ServerApp.disable_check_xsrf=True",
    ],
    { cwd: rootDir, detached: true, stdio: "ignore" }
  );
  server.on("error", () => {
    ready = false;
  });

  ready = await waitForStatus(baseUrl, token);
  if (!ready) return;

  setJupyterConfig({
    host: "localhost",
    port,
    token,
    baseUrl,
    wsUrl: `ws://localhost:${port}`,
  } as JupyterConfig);

  await checkRtcAvailability();
}, 90_000);

afterAll(async () => {
  // Drop any live sockets so they don't keep the event loop alive.
  for (const path of [...connectedNotebooks.keys()]) evictNotebook(path);
  setJupyterConfig(null);
  if (server?.pid) {
    try {
      process.kill(-server.pid, "SIGKILL");
    } catch {
      try {
        server.kill("SIGKILL");
      } catch {
        /* already gone */
      }
    }
  }
  if (rootDir) await rm(rootDir, { recursive: true, force: true });
}, 30_000);

// The runtime `ready` flag isn't visible at collection time, so the tests
// themselves early-return with an assertion that the server came up. If the
// spawn failed entirely, that surfaces as a clear failure locally; guard with
// an env opt-out for constrained CI.
const suite = process.env.SKIP_COLLAB_INTEGRATION ? describe.skip : describe;

suite("collab persistence integration (real jupyter-collaboration server)", () => {
  it("A. round-trips edits to disk (insert + update + save_notebook)", async () => {
    expect(ready, "real jupyter server must be reachable").toBe(true);

    const marker = "print('round-trip-A')";
    await cellWriteHandlers["insert_cell"]({
      path: NB_PATH,
      source: marker,
      cell_type: "code",
    });
    await cellWriteHandlers["update_cell"]({
      path: NB_PATH,
      index: 0,
      source: "# updated-original",
    });

    const saveRes = await connectionHandlers["save_notebook"]({ path: NB_PATH });
    expect(textOf(saveRes)).toContain("VERIFIED");
    // Instrumentation for the root_dir-vs-cwd case (Coiled issue): the verified
    // save must report WHERE the server persisted the room, so a mismatch with a
    // kernel's os.getcwd() is diagnosable rather than read as data loss.
    expect(textOf(saveRes)).toContain("Server path");

    const onDisk = await diskSources(rootDir);
    expect(onDisk).toContain(marker);
    expect(onDisk).toContain("# updated-original");
  }, 60_000);

  it("B. never reports a desynced edit as saved (self-heal or throw, never a false verified)", async () => {
    expect(ready, "real jupyter server must be reachable").toBe(true);

    // Establish a live, synced connection and a known-good baseline on disk.
    await getNotebookConnection(NB_PATH);
    await cellWriteHandlers["update_cell"]({
      path: NB_PATH,
      index: 0,
      source: "# baseline-B",
    });
    await connectionHandlers["save_notebook"]({ path: NB_PATH });
    expect(await diskSources(rootDir)).toContain("# baseline-B");

    // Simulate the reported failure: the collab socket drops but the cached
    // connection is NOT evicted. y-websocket's disconnect() clears
    // synced/wsconnected and won't auto-reconnect, so any edit made now would
    // sit in a dead local buffer — exactly the desync the bug lost data in.
    const cached = connectedNotebooks.get(NB_PATH);
    expect(cached, "expected a cached connection to desync").toBeTruthy();
    (cached!.provider as any).disconnect();

    // Now edit through the real handler and save. The fix must make this either
    // persist (gate self-heals the dead socket) or fail loudly — never a silent
    // "verified" over stale disk.
    const desyncMarker = "# desync-edit-B";
    let threw = false;
    try {
      await cellWriteHandlers["update_cell"]({
        path: NB_PATH,
        index: 0,
        source: desyncMarker,
      });
      await connectionHandlers["save_notebook"]({ path: NB_PATH });
    } catch {
      threw = true;
    }

    const persisted = (await diskSources(rootDir)).includes(desyncMarker);
    // The contract: the edit reached disk (self-healed) OR the tool refused.
    // The pre-fix code did neither — it returned "verified" while disk kept the
    // baseline — so this assertion is the regression guard.
    expect(
      persisted || threw,
      "desynced edit was silently reported saved but never reached disk"
    ).toBe(true);
  }, 60_000);
});
