/**
 * Persistence verification — the one place that answers "is this notebook's live
 * room actually saved to the file the server serves?" It force-saves the room
 * and reads the result back through the server's Contents API (which resolves
 * against the server's own root_dir), then compares content signatures.
 *
 * This is the durable-integrity checkpoint behind `save_notebook` and
 * `troubleshoot`. It catches the failure class from the collab-desync reports:
 * edits that land in a room which is not the one persisted to the target file
 * (a second overlapping server, or a server root_dir that differs from where the
 * caller is looking) — where a plain "save succeeded" reply is a lie.
 */

import { apiFetch, getNotebookConnection, saveNotebook } from "./connection.js";
import { contentSignature, countPeers, isProviderSynced } from "./helpers.js";

export interface PersistCheck {
  /** Server's reply to the forced save: "success" | "skipped" | "failed". */
  saveStatus: string;
  /** Provider is connected and synced to the server room. */
  synced: boolean;
  /** Remote clients (browser tabs) in the room besides this MCP. */
  peers: number;
  /** Cells in the live room. */
  roomCells: number;
  /** The file exists on the connected server. */
  diskExists: boolean;
  /**
   * Server-normalized path returned by the Contents API (relative to the
   * server's root_dir). Surfacing it makes a root/cwd mismatch diagnosable: the
   * room persists HERE, which may differ from a kernel `open()`'s cwd-relative
   * path.
   */
  serverPath: string | null;
  lastModified: string | null;
  /**
   * True when the on-disk file (as the server serves it) matches the live room
   * after a forced save. False means split-brain: the edits are not reaching
   * this file.
   */
  persisted: boolean;
}

/**
 * Force-save `path`'s room and verify it round-trips to disk. Never throws for
 * a mere mismatch — it reports one via `persisted: false` so callers can frame
 * their own error/diagnostics. May throw only on a transport failure (e.g. the
 * Contents API is unreachable).
 */
export async function verifyPersistedToDisk(path: string): Promise<PersistCheck> {
  const { doc, provider } = await getNotebookConnection(path);
  const synced = isProviderSynced(provider);
  const peers = countPeers(provider);
  const roomCells = [...doc.getArray("cells")];
  const roomSig = contentSignature(roomCells);

  const { status: saveStatus } = await saveNotebook(path);

  let diskExists = false;
  let serverPath: string | null = null;
  let lastModified: string | null = null;
  let diskSig: string | null = null;
  const res = await apiFetch(`/api/contents/${encodeURIComponent(path)}?content=1`);
  if (res.ok) {
    const nb = await res.json();
    diskExists = true;
    serverPath = nb?.path ?? null;
    lastModified = nb?.last_modified ?? null;
    diskSig = contentSignature(nb?.content?.cells ?? []);
  }

  return {
    saveStatus,
    synced,
    peers,
    roomCells: roomCells.length,
    diskExists,
    serverPath,
    lastModified,
    persisted: diskSig !== null && diskSig === roomSig,
  };
}
