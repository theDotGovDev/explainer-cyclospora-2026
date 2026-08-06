# explainer-cyclospora-2026

A static site providing practical, source-cited risk information about the 2026 U.S.
*Cyclospora* outbreak. The focus is **actionable risk assessment** — what to eat, what to
substitute, and what each mitigation is actually worth — rather than a general disease
overview.

**This is not medical advice.** It is an independent, best-effort explainer with no
affiliation to CDC, FDA, or any company. See the disclaimers in the site footer, which are
part of every page.

## What's here

| Path | Purpose |
| --- | --- |
| `data/outbreak.json` | Outbreak status, recall details, evidence caveats, pathogen biology |
| `data/foods.json` | The per-food risk table: status, risk estimates, mitigations, residual risk |
| `data/sources.json` | Every source, graded by tier, with a stable citation id |
| `build.py` | Renders the site from the JSON. No dependencies. |
| `tools/validate.py` | Correctness checks — run in CI, blocks merge on failure |
| `tools/check_links.py` | Advisory check that every cited URL still resolves |
| `site/` | Generated output — commit this; it is what gets served |

The JSON files are the canonical record. Don't hand-edit `site/*.html`; it will be
overwritten.

## Build

```sh
python3 build.py && python3 tools/validate.py
```

Requires Python 3 only — no packages, no toolchain. To preview:

```sh
python3 -m http.server -d site 8000
```

## Automation

> **These workflows are written but not yet active.** They sit in `ci/workflows/` rather
> than `.github/workflows/`, because the credentials used to author them lack GitHub's
> `workflow` OAuth scope. See [`ci/README.md`](ci/README.md) for the one-command install.

| Workflow | Trigger | What it does |
| --- | --- | --- |
| `ci.yml` | push, PR | Builds, asserts committed `site/` matches `data/`, runs the validator. Also checks source links (advisory). |
| `pages.yml` | push to `main` | Rebuilds, validates, deploys to GitHub Pages. Won't publish a page that fails validation. |
| `freshness.yml` | weekly | Opens or updates a `stale-data` issue when `as_of` ages past 21 days. |

`tools/validate.py` enforces the things that would otherwise rot silently:

- every citation resolves, and inline `[n]` markers match the sources page numbering;
- every citation carries a sourcing marker, so no claim appears unlabeled;
- all four core disclaimers are present on every page;
- risk values are hedged — an unhedged point value like `1 in 50,000` fails the build,
  because these are estimates and must read as estimates;
- HTML is well-formed and external links carry `rel`;
- the `as_of` date is present on every page, not in the future, and not stale.

GitHub Pages needs to be enabled once in **Settings → Pages → Source: GitHub Actions**
before `pages.yml` can deploy.

## Sourcing markers

Every claim is tagged with where it came from, and moving numbers are tagged with the date
they describe:

- **agency** — backed by a government, public health or peer-reviewed source
- **agency + news** — a mix of agency sourcing and news reporting
- **news** — news or consumer reporting only, not confirmed against a primary document

Markers are derived automatically from the `tier` of each cited source, so they cannot
drift out of sync with the actual citations. Note the distinction the site makes explicitly:
an **agency** marker means an agency *originated* the claim, not that it was read off the
agency's own page — see the limitation below.

## Editorial rules

These exist because the whole value of the project is that its numbers can be trusted.

1. **Every factual claim carries a source id.** If you add a claim, add it to the
   `sources` array on that record. The build enforces that the id resolves.
2. **Distinguish evidence tiers.** Agency findings, active tracebacks, and historical
   associations are different things and are labeled differently in the `status` field.
   Never promote a traceback to a confirmed finding.
3. **Label estimates as estimates.** Every probability on this site was derived by this
   project, not published by an agency. Order-of-magnitude ranges only — the underlying
   uncertainty doesn't support more precision.
4. **Show the method.** `site/methodology.html` documents the calculation, the assumptions,
   and a "known weaknesses" section. If you change how a number is derived, update it.
5. **Show disagreement rather than resolving it silently.** Published case counts conflict
   across sources and snapshot dates. Where they do, present the range.
6. **Date everything.** Update `as_of` and `data_current_through` in `outbreak.json` on
   every content change. A stale number presented as current is the main failure mode here.
7. **Don't drive people away from produce.** The health benefit of fruits and vegetables
   outweighs these risks for nearly everyone. The purpose is to help readers substitute
   *within* produce.

## Known limitation in the current data

The environment in which this site was first built **could not reach `cdc.gov` or `fda.gov`**
— both were blocked at the network egress layer. Agency figures were taken from
search-indexed summaries of those pages and from secondary reporting that cites them, not
from a direct read of the primary documents.

This is disclosed on the site itself rather than papered over. **Before relying on this
content, re-verify every figure in `data/outbreak.json` against the primary CDC and FDA
pages** listed in `data/sources.json`. Where they differ, the agencies are right.

## Updating for a new outbreak development

1. Re-verify the primary sources and update `data/outbreak.json` (counts, dates, recall
   scope, caveats).
2. If a new commodity is named, add or move its row in `data/foods.json` and adjust the
   `status` field. Confirming cilantro or cucumbers, for example, should raise those rows
   and lower iceberg's share.
3. Bump `as_of` and `data_current_through`.
4. Run `python3 build.py` and commit both the data and the generated `site/`.
