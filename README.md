# explainer-cyclospora-2026

**→ [thedotgovdev.github.io/explainer-cyclospora-2026](https://thedotgovdev.github.io/explainer-cyclospora-2026/)**

A static site providing practical, source-cited risk information about the 2026 U.S.
*Cyclospora* outbreak. The focus is **actionable risk assessment** — what to eat, what to
substitute, and what each mitigation is actually worth — rather than a general disease
overview.

| Page | |
| --- | --- |
| [Risk by food](https://thedotgovdev.github.io/explainer-cyclospora-2026/) | Per-food estimates, what the odds mean, outbreak status, when to seek care |
| [Methodology](https://thedotgovdev.github.io/explainer-cyclospora-2026/methodology.html) | How every number was derived, the label glossary, known weaknesses |
| [Sources](https://thedotgovdev.github.io/explainer-cyclospora-2026/sources.html) | Every source, graded by authority |

**This is not medical advice**, and **it was generated using AI** — see the disclaimers in
the footer of every page. It is an independent explainer with no affiliation to CDC, FDA,
or any company, and carries no agency branding deliberately.

## What's here

| Path | Purpose |
| --- | --- |
| `data/outbreak.json` | Outbreak status, recall details, evidence caveats, pathogen biology |
| `data/foods.json` | The per-food risk records: status, estimates, mitigations, evidence basis |
| `data/comparisons.json` | Real-world risk anchors, each on a per-single-occasion basis |
| `data/sources.json` | Every source, graded by tier, with a stable citation id |
| `build.py` | Renders the site from the JSON. No dependencies. |
| `icons.py` | Inline SVG sprite and logo. All original artwork — no agency marks. |
| `tools/validate.py` | Correctness checks — run in CI, fails the build |
| `tools/check_links.py` | Advisory check that every cited URL still resolves |
| `site/` | Generated output — commit it; it is what gets served |

The JSON files are the canonical record. Don't hand-edit `site/*.html`; it gets overwritten.

## Build

```sh
python3 build.py && python3 tools/validate.py
python3 -m http.server -d site 8000     # preview
```

Python 3 only — no packages, no toolchain.

## Automation

| Workflow | Trigger | What it does |
| --- | --- | --- |
| `ci.yml` | push, PR | Builds, asserts committed `site/` matches `data/`, runs the validator. Source-link check runs separately as advisory. |
| `pages.yml` | push to `main` | Rebuilds, validates, deploys to Pages. Won't publish a page that fails validation. |
| `freshness.yml` | weekly | Opens or updates a `stale-data` issue once `as_of` ages past 21 days. |

Note that `tools/validate.py` **fails** on data older than 21 days, so a stale `as_of`
stops the site redeploying until the data is refreshed. That is the guard working, not a
bug.

## What the validator enforces

These checks exist because the site makes health claims, and each one is here because
something actually went wrong:

- every citation resolves — in `foods.json`, `outbreak.json` **and** `comparisons.json`;
  an unknown source id aborts the build rather than silently dropping the citation;
- inline `[n]` markers match the sources-page numbering;
- comparison anchors marked as derived must show their arithmetic, and every anchor
  must have either a source or a note saying where the number came from;
- every claim carries a sourcing marker, and every food carries an evidence-basis label;
- anything claiming a reference actually cites one, or must be marked `extrapolated`;
- every badge links to a definition that exists on the methodology page;
- the displayed risk band agrees with the numeric range (two foods with identical ranges
  were once shown in different bands);
- every icon name exists in the sprite (a missing one renders as an invisible no-op);
- risk values are hedged — an unhedged `1 in 50,000` fails the build, because these are
  estimates and must read as estimates;
- all five core disclaimers, including the AI-generation notice, are on every page;
- HTML is well-formed, external links carry `rel`, and `as_of` is present and not stale.

## The two labelling systems

Kept separate on purpose, and given separate colour channels, because they answer
different questions and can disagree.

**Outbreak status** — what investigators have found about the food. `confirmed`,
`under-traceback`, `linked-by-recall`, `historical`, `not-implicated`.

**Evidence basis** — how *our* risk claim for that food is grounded. `named-2026`,
`named-historical`, `general-guidance`, `extrapolated`.

A food can be strongly evidenced as low risk, or weakly evidenced as high risk. One scale
cannot say both, so risk and status share a warm ramp while evidence and sourcing share a
cool one. Every badge links to a full definition in the methodology glossary.

**In every case the risk number itself is our estimate.** A citation showing a food was
named in the outbreak does not mean an agency published a per-serving probability for it —
none has, for any food.

## Editorial rules

1. **Every factual claim carries a source id.** The build enforces that it resolves.
2. **Say whether a food is referenced or extrapolated.** Never let a citation about
   pathogen behaviour imply that a source named the food.
3. **Never promote a traceback to a confirmed finding.** They are different claims.
4. **Label estimates as estimates.** Order-of-magnitude ranges only.
5. **Keep units comparable.** Risks are per serving; comparison anchors are converted to a
   single occasion, with the arithmetic shown. Never set a per-serving figure beside a
   per-year or per-lifetime one.
6. **Show disagreement rather than resolving it silently.** Published case counts conflict
   across sources and dates; present the range.
7. **Date everything.** Bump `as_of` and `data_current_through` on every content change.
8. **Don't drive people away from produce.** The benefit of fruits and vegetables
   outweighs these risks for nearly everyone. Help readers substitute *within* produce.

## Known limitations

**The outbreak figures have not been verified against primary sources.** The environment
this was built in could not reach `cdc.gov` or `fda.gov` — both blocked at the network
egress layer. Agency figures came from search-indexed summaries and secondary reporting
that cites them. Re-verify everything in `data/outbreak.json` against the primary pages
listed in `data/sources.json`; where they differ, the agencies are right.

**No clinician or epidemiologist has reviewed this.** The risk model is the part most
worth expert review.

A note for anyone running the link checker: `fda.gov` returns HTTP 404 to automated
requests for every URL including its own homepage, where `cdc.gov` returns 403. Both are
blocking automation and neither means the page is missing. `tools/check_links.py` handles
this by probing the host root before calling a link dead.

## Updating for a new outbreak development

1. Re-verify the primary sources; update `data/outbreak.json` (counts, dates, recall
   scope, caveats).
2. If a new commodity is named, add or update its record in `data/foods.json`, and move it
   from `extrapolated` to a referenced evidence basis with the citation.
3. Bump `as_of` and `data_current_through`.
4. Run `python3 build.py && python3 tools/validate.py`, then commit the data *and* the
   regenerated `site/`.
