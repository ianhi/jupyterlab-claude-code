/**
 * Up-front tool-argument validation. Rejecting a bad call here — rather than
 * letting a wrong or unknown parameter silently become `undefined` and surface
 * as a misleading downstream error, or a spurious "success" that edited nothing
 * (issue #23) — is a data-integrity guardrail, not just ergonomics.
 */

import { closest, distance } from "fastest-levenshtein";

export interface ObjectSchema {
  properties?: Record<string, any>;
  required?: string[];
}

/** Pick the accepted param name closest to `unknown`, if any is plausibly a typo of it. */
export function suggestParam(unknown: string, accepted: string[]): string | undefined {
  const u = unknown.toLowerCase();
  // Compound-name guesses (nb_path → path, kernelname → kernel_name) don't have
  // a small edit distance, so treat substring containment as a strong match first.
  const contained = accepted.find((name) => {
    const n = name.toLowerCase();
    return n.length >= 3 && (u.includes(n) || n.includes(u));
  });
  if (contained) return contained;

  if (accepted.length === 0) return undefined;
  const best = closest(u, accepted.map((a) => a.toLowerCase()));
  // Map back to the original casing and only suggest a genuine near-miss.
  const orig = accepted.find((a) => a.toLowerCase() === best);
  return orig !== undefined && distance(u, best) <= Math.max(2, Math.ceil(best.length / 3))
    ? orig
    : undefined;
}

/**
 * Validate one object against an object schema, appending human-readable
 * problems to `problems`. Recurses into array-of-object properties so a bad
 * *element* (e.g. a batch_update_cells item passing `cell_id` instead of the
 * required `index`) is caught rather than silently coerced to `undefined`
 * downstream — the failure mode behind issue #23.
 */
export function validateObject(
  obj: Record<string, unknown>,
  schema: ObjectSchema,
  label: string,
  problems: string[]
): void {
  const accepted = Object.keys(schema.properties ?? {});
  const required = schema.required ?? [];
  const where = label ? ` in ${label}` : "";

  for (const r of required) {
    if (obj[r] === undefined) problems.push(`missing required parameter '${r}'${where}`);
  }
  for (const key of Object.keys(obj)) {
    if (accepted.includes(key)) continue;
    const suggestion = suggestParam(key, accepted);
    problems.push(
      `unrecognized parameter '${key}'${where}` +
        (suggestion ? ` — did you mean '${suggestion}'?` : "")
    );
  }

  // Recurse into array-typed properties whose items are objects.
  for (const key of accepted) {
    const prop = schema.properties![key];
    if (prop?.type === "array" && prop.items?.type === "object" && Array.isArray(obj[key])) {
      (obj[key] as unknown[]).forEach((item, i) => {
        if (item && typeof item === "object" && !Array.isArray(item)) {
          validateObject(item as Record<string, unknown>, prop.items, `${key}[${i}]`, problems);
        }
      });
    }
  }
}

/**
 * Throw if `args` don't satisfy `schema`. Rejects both missing required params
 * and *unrecognized* ones (top-level and inside array items), and suggests the
 * closest accepted name for a likely typo. A no-op when `schema` is undefined
 * (unknown tool — handled elsewhere).
 */
export function validateArgs(
  schema: ObjectSchema | undefined,
  name: string,
  args: Record<string, unknown>
): void {
  if (!schema) return;

  const problems: string[] = [];
  validateObject(args, schema, "", problems);
  if (problems.length === 0) return;

  const accepted = Object.keys(schema.properties ?? {})
    .map((p) => ((schema.required ?? []).includes(p) ? `${p} (required)` : p))
    .join(", ");
  throw new Error(
    `Tool '${name}' called with invalid parameters:\n` +
      problems.map((p) => `  • ${p}`).join("\n") +
      `\nAccepted parameters: ${accepted || "(none)"}.`
  );
}
