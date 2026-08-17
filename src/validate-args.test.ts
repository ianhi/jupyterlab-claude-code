import { describe, it, expect } from "vitest";
import { validateArgs, type ObjectSchema } from "./validate-args.js";
import { toolSchemas } from "./schemas.js";

/** The real inputSchema for a shipped tool, so these tests track the actual API. */
function schemaFor(name: string): ObjectSchema {
  const t = toolSchemas.find((s) => s.name === name);
  if (!t) throw new Error(`no schema for ${name}`);
  return t.inputSchema as ObjectSchema;
}

/**
 * The PRE-FIX validation: it only complained about a missing *required*
 * top-level param and returned early otherwise, so unknown keys — including a
 * whole array item missing its required `index` — sailed through as success.
 * Embedded here so each test can assert the exact bug the new validator closes
 * (red under this, green under validateArgs).
 */
function oldValidateArgs(schema: ObjectSchema, args: Record<string, unknown>): void {
  const required = schema.required ?? [];
  const missing = required.filter((r) => args[r] === undefined);
  if (missing.length === 0) return; // ← the bug: no unknown-key / array-item checks
  throw new Error(`missing: ${missing.join(", ")}`);
}

describe("validateArgs — issue #23 regression", () => {
  it("batch_update_cells: item with cell_id but no index is REJECTED (was a silent no-op)", () => {
    const schema = schemaFor("batch_update_cells");
    const args = { path: "nb.ipynb", updates: [{ cell_id: "abc123", source: "x=1" }] };

    // Pre-fix behavior: accepted silently → the reported "Updated 3 cells" /
    // cell[undefined] data-loss bug.
    expect(() => oldValidateArgs(schema, args)).not.toThrow();

    // Fixed behavior: the bad array item is caught.
    expect(() => validateArgs(schema, "batch_update_cells", args)).toThrow(/index/);
    expect(() => validateArgs(schema, "batch_update_cells", args)).toThrow(/cell_id/);
    expect(() => validateArgs(schema, "batch_update_cells", args)).toThrow(/updates\[0\]/);
  });

  it("update_cell: an unknown top-level param is REJECTED even when required are present", () => {
    const schema = schemaFor("update_cell");
    const args = { path: "nb.ipynb", source: "x=1", cellType: "markdown" };

    expect(() => oldValidateArgs(schema, args)).not.toThrow();
    expect(() => validateArgs(schema, "update_cell", args)).toThrow(/cellType/);
  });

  it("update_cell: cell_type IS now an accepted param (no longer dropped)", () => {
    const schema = schemaFor("update_cell");
    expect(() =>
      validateArgs(schema, "update_cell", { path: "nb.ipynb", source: "# hi", cell_type: "markdown" })
    ).not.toThrow();
  });

  it("still rejects a genuinely missing required param", () => {
    const schema = schemaFor("update_cell");
    expect(() => validateArgs(schema, "update_cell", { path: "nb.ipynb" })).toThrow(/source/);
  });

  it("accepts a fully valid call", () => {
    const schema = schemaFor("batch_update_cells");
    expect(() =>
      validateArgs(schema, "batch_update_cells", {
        path: "nb.ipynb",
        updates: [{ index: 0, source: "x=1" }, { index: 1, source: "y=2" }],
      })
    ).not.toThrow();
  });

  it("suggests the closest accepted name for a typo'd key", () => {
    const schema = schemaFor("insert_cell");
    expect(() => validateArgs(schema, "insert_cell", { notebook_path: "nb.ipynb", source: "x" }))
      .toThrow(/did you mean 'path'/);
  });

  it("no-op when the tool schema is unknown", () => {
    expect(() => validateArgs(undefined, "mystery_tool", { anything: 1 })).not.toThrow();
  });
});
