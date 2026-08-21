#!/usr/bin/env node
// Builds sourcey.config.ts tabs from the real Starlight content tree,
// mapping index.md/index.mdx files to their directory slug (matching
// Starlight's own routing) instead of a literal ".../index" slug.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, basename, extname } from "node:path";

const listPath = process.argv[2]; // all_pages.txt (relative paths, one per line)
const lines = readFileSync(listPath, "utf-8").trim().split("\n").filter(Boolean);

// root index.mdx handled separately (overview tab) -- exclude from directory groups
const contentPages = lines.filter((p) => p !== "index.mdx");

function toSlug(relPath) {
  const ext = extname(relPath);
  const base = basename(relPath, ext);
  if (base === "index") {
    const dir = dirname(relPath);
    return dir === "." ? "" : dir; // "" only for true root, already excluded
  }
  const noExt = relPath.slice(0, -ext.length);
  return noExt;
}

// group by top-level directory (first path segment) to mirror the real sidebar sections
const groups = new Map();
for (const rel of contentPages) {
  const top = rel.split("/")[0];
  const slug = toSlug(rel);
  if (!groups.has(top)) groups.set(top, []);
  groups.get(top).push({ slug, rel });
}

// sanity: detect slug collisions
const seenSlugs = new Map();
for (const [top, pages] of groups) {
  for (const { slug, rel } of pages) {
    if (seenSlugs.has(slug)) {
      console.error(`COLLISION: slug "${slug}" used by both ${seenSlugs.get(slug)} and ${rel}`);
      process.exitCode = 1;
    }
    seenSlugs.set(slug, rel);
  }
}

// Human-readable labels for each top-level directory, so llms.txt gets
// section headings like "Agent Health" instead of the raw slug
// "agent-health". Sourced from docs/starlight-docs/astro.config.mjs, the
// Starlight sidebar config, which is the honest source for what a maintainer
// calls each section -- NOT invented here. Two kinds of source, both
// verified by reading that file directly:
//
//  - CLEAN MATCH: a sidebar entry ("autogenerate: { directory: X }", or a
//    hand-written group whose every item link falls under exactly one
//    directory) maps 1:1 onto one of our directories. That sidebar label is
//    used verbatim.
//  - NO CLEAN MATCH: the sidebar groups several of our directories together
//    for navigation ergonomics ("Alerting" spans alerting/, slo/,
//    anomaly-detection/, forecasting/; "SDKs, MCP & Clients" spans two
//    send-data pages plus mcp/) or references a page outside the directory
//    ("Agent Observability" includes one send-data page alongside
//    ai-observability/*). Forcing those merges onto our per-directory
//    sections would require hand-picked page-level exceptions, which is
//    inventing taxonomy, not reading it. For these, the label below is a
//    plain title-case of the slug with known tech acronyms capitalized.
//
// Verified against docs/starlight-docs/astro.config.mjs at commit 6fd43fa:
const DIRECTORY_LABELS = {
  "agent-evals": "Agent Evals", // sidebar: hand-written group labelled 'Agent Evals', every item under /agent-evals/
  "agent-health": "Agent Health", // sidebar: autogenerate directory 'agent-health'
  "ai-observability": "AI Observability", // no clean match (sidebar's "Agent Observability" group also links one send-data page) -- title-case + AI acronym
  "alerting": "Alerting", // no clean match (sidebar's "Alerting" group also spans slo/, anomaly-detection/, forecasting/) -- title-case, happens to equal the sidebar group's own name
  "anomaly-detection": "Anomaly Detection", // no clean match (item lives inside the merged "Alerting" group) -- title-case, happens to equal the sidebar item's own label
  "apm": "Application Monitoring", // sidebar: autogenerate directory 'apm'
  "claude-code": "Claude Code", // sidebar: autogenerate directory 'claude-code'
  "dashboards": "Dashboards & Visualize", // sidebar: hand-written group, every item under /dashboards/
  "deploy": "Deploy to Cloud", // sidebar: hand-written group, every item under /deploy/
  "forecasting": "Forecasting", // no clean match (item lives inside the merged "Alerting" group) -- title-case, happens to equal the sidebar item's own label
  "get-started": "Get Started", // sidebar: hand-written group, every item under /get-started/
  "investigate": "Discover", // sidebar: autogenerate directory 'investigate', but the group is LABELED "Discover" -- not a slug-derived name, verify before assuming otherwise
  "mcp": "MCP", // no clean match (grouped with 2 send-data pages under "SDKs, MCP & Clients") -- acronym
  "ppl": "PPL - Query Language", // sidebar: hand-written group, every item under /ppl/
  "send-data": "Send Data", // sidebar: hand-written group, every item (incl. nested autogenerate subsections) under /send-data/
  "slo": "SLO", // no clean match (grouped inside merged "Alerting") -- acronym
};

// Fallback for any future top-level directory not yet reviewed against the
// sidebar above: plain title-case with a small acronym allowlist, so a new
// directory doesn't silently produce an unlabelled or wrong section instead
// of failing loudly. NOT a substitute for adding a reviewed entry above.
const ACRONYMS = new Set(["ai", "mcp", "ppl", "slo", "apm", "sdk", "api"]);
function fallbackLabel(slug) {
  return slug
    .split("-")
    .map((word) => (ACRONYMS.has(word) ? word.toUpperCase() : word[0].toUpperCase() + word.slice(1)))
    .join(" ");
}

function labelFor(dir) {
  if (DIRECTORY_LABELS[dir]) return DIRECTORY_LABELS[dir];
  console.error(`WARNING: no reviewed sidebar label for directory "${dir}", using algorithmic fallback "${fallbackLabel(dir)}". Add a reviewed entry to DIRECTORY_LABELS in gen-config.mjs.`);
  return fallbackLabel(dir);
}

// One TAB per top-level directory, not one tab with many groups, because
// sourcey's own llms.txt renderer (dist/renderer/llms.js, generateLlmsTxt)
// only ever emits an H2 ("## {tab.label}") per TAB -- it iterates
// navigation.tabs and filters pages by tab, but for a "markdown" source kind
// it prints a flat list straight from tabPages with no per-group heading at
// all. Groups exist for the adapter's own internal organisation but are
// invisible in llms.txt output. Confirmed by reading generateLlmsTxt: the
// markdown branch does `lines.push(`- [${doc.title}](${href})...`)` for
// every page in the tab with no group-keyed loop. So one H2 per real section
// requires one TAB per section, each with slug === its directory name so
// page output paths (which already start with "<directory>/...") pass
// through tabPath() unchanged instead of double-nesting -- verified this
// does not perturb any URL: pageOutputPath()'s tabPath(tabSlug, file) only
// prefixes when `file` does not already start with "<tabSlug>/", and every
// page's slug here already starts with its own directory name.
const overviewTab = {
  tab: "Overview",
  slug: "",
  pages: ["index"],
};

const dirTabs = [...groups.entries()]
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([top, pages]) => {
    const sortedPages = pages.map((p) => p.slug).sort();
    return { tab: labelFor(top), slug: top, pages: sortedPages };
  });

// Overview tab must be emitted FIRST: sourcey's resolveSiteSummary() (same
// file) takes the frontmatter `description` of the first page across ALL
// tabs, in tabs-array order, as the whole site's "> tagline" line. That is
// unaffected by moving from groups to tabs -- it is still first-page-wins
// across the full assembled `pages` array -- but it does mean the Overview
// tab must stay first in this array regardless of alphabetical directory
// order, or the tagline bug returns.
const allTabs = [overviewTab, ...dirTabs];

function tabBlock({ tab, slug, pages }) {
  return `      {
        tab: ${JSON.stringify(tab)},
        slug: ${JSON.stringify(slug)},
        source: markdown({
          groups: [{ group: ${JSON.stringify(slug || "overview")}, pages: ${JSON.stringify(pages)} }],
        }),
      }`;
}

const configTs = `// AUTO-GENERATED by gen-config.mjs. Do not hand-edit -- regenerate instead.
import { defineConfig, markdown } from "sourcey";

export default defineConfig({
  name: "OpenSearch Observability Stack",
  siteUrl: "https://observability.opensearch.org",
  baseUrl: "/docs",
  prettyUrls: "slash",
  repo: "https://github.com/opensearch-project/observability-stack",
  editBranch: "main",
  editBasePath: "docs/starlight-docs/src/content/docs",
  navigation: {
    tabs: [
${allTabs.map(tabBlock).join(",\n")},
    ],
  },
});
`;

writeFileSync("sourcey.config.ts", configTs);
console.log(`Wrote sourcey.config.ts with ${contentPages.length} pages across ${allTabs.length} tabs (1 overview + ${dirTabs.length} sections).`);
console.log("Sections:", dirTabs.map((t) => `${t.tab} (${t.slug})`).join(", "));
