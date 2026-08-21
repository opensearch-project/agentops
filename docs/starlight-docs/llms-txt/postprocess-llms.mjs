#!/usr/bin/env node
// Rewrites site-relative markdown links in a sourcey-generated llms.txt into
// fully-qualified links, because the file is served at the SITE ROOT
// (https://observability.opensearch.org/llms.txt) while every entry points
// under /docs/. An LLM fetching /llms.txt out of context has no HTML <base>
// and no page origin to resolve a relative link against, so a bare "/docs/..."
// link is only meaningful if the reader already knows the site -- exactly the
// failure the file exists to avoid. Both exemplars cited by opensearch-project/
// observability-stack issue #262 (Cloudflare, Stripe) ship fully-qualified
// links in their own llms.txt for this reason.
//
// Sourcey's own llms.txt renderer (dist/renderer/llms.js) always emits
// site-relative hrefs via toPublicPath() and has no config option to use the
// absolute toPublicUrl() variant instead, so this has to be a post-process
// step run on the file sourcey writes, not a sourcey.config.ts setting.
//
// Usage: node postprocess-llms.mjs <path-to-llms.txt-in-place>
import { readFileSync, writeFileSync } from "node:fs";

const SITE_URL = "https://observability.opensearch.org";
const filePath = process.argv[2];
if (!filePath) {
  console.error("Usage: node postprocess-llms.mjs <path-to-llms.txt>");
  process.exit(1);
}

const before = readFileSync(filePath, "utf-8");

// The H1 ("# ...") and tagline ("> ...") lines carry no markdown links and
// must be byte-identical before and after. Capture them up front so we can
// assert they didn't move.
const beforeLines = before.split("\n");
const h1Before = beforeLines[0];
const taglineBefore = beforeLines[2];

// Every entry line looks like "- [Title](/some/path/): description". Rewrite
// only "](/..." -> "](https://observability.opensearch.org/...". This never
// touches the H1 or tagline (neither contains "](/"), and it is naturally
// idempotent: a link that has already been rewritten starts with "](https://"
// not "](/", so re-running this script on its own output is a no-op.
const relativeLinkPattern = /\]\(\//g;
const relativeLinkCount = (before.match(relativeLinkPattern) ?? []).length;

if (relativeLinkCount === 0) {
  console.error("No site-relative links found (\"](/\"). Refusing to run: either " +
    "the file is already fully-qualified (fine, but nothing to do) or the input " +
    "is not the llms.txt this script expects. Aborting without writing.");
  process.exit(1);
}

const after = before.replace(relativeLinkPattern, `](${SITE_URL}/`);

// --- Assertions: count-based, not spot-checked. ---

// 1. Every relative link line got rewritten: zero bare "](/" survive.
const remainingRelative = (after.match(relativeLinkPattern) ?? []).length;
if (remainingRelative !== 0) {
  throw new Error(`${remainingRelative} relative link(s) survived the rewrite -- expected 0.`);
}

// 2. The rewritten link count matches the original relative link count
//    exactly (nothing added, nothing dropped).
const qualifiedCount = (after.match(new RegExp(`\\]\\(${SITE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/`, "g")) ?? []).length;
if (qualifiedCount !== relativeLinkCount) {
  throw new Error(`Expected ${relativeLinkCount} fully-qualified links, found ${qualifiedCount}.`);
}

// 3. No double-prefix: the origin must never appear twice in a row inside a
//    single link (e.g. "https://observability.opensearch.orghttps://...").
const doublePrefixPattern = new RegExp(`${SITE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}${SITE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`);
if (doublePrefixPattern.test(after)) {
  throw new Error("Double-prefixed origin detected in output. Aborting without writing.");
}

// 4. H1 and tagline lines are untouched.
const afterLines = after.split("\n");
if (afterLines[0] !== h1Before) {
  throw new Error(`H1 line changed. Before: "${h1Before}" After: "${afterLines[0]}"`);
}
if (afterLines[2] !== taglineBefore) {
  throw new Error(`Tagline line changed. Before: "${taglineBefore}" After: "${afterLines[2]}"`);
}

writeFileSync(filePath, after);
console.log(`Rewrote ${relativeLinkCount} relative links to fully-qualified ${SITE_URL}/... links.`);
console.log(`Remaining relative links: ${remainingRelative}. Double-prefix check: clean. H1/tagline: unchanged.`);
