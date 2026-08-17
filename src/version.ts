import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

/**
 * The server's real version, read from package.json at startup. Both src/ and
 * the compiled dist/ sit one directory below package.json, so the relative URL
 * resolves the same in dev and in the published package. Falls back to
 * "unknown" rather than throwing if the file can't be read.
 */
export const VERSION: string = (() => {
  try {
    const pkgPath = fileURLToPath(new URL("../package.json", import.meta.url));
    return JSON.parse(readFileSync(pkgPath, "utf8")).version ?? "unknown";
  } catch {
    return "unknown";
  }
})();
