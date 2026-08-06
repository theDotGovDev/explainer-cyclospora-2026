# Workflows (pending install)

These three GitHub Actions workflows are ready to use but are **not yet active**, because
they live here rather than in `.github/workflows/`.

They could not be committed to `.github/workflows/` directly: the credentials available to
the automated session that wrote them lack GitHub's `workflow` OAuth scope, which is
required to create or modify workflow files. That is a credential limitation, not a problem
with the workflows themselves.

## Installing them

Any account with normal push access can activate them in one step:

```sh
mkdir -p .github/workflows
git mv ci/workflows/*.yml .github/workflows/
git rm ci/README.md
git commit -m "Activate CI, Pages and freshness workflows"
git push
```

Then enable Pages once, in **Settings → Pages → Source: GitHub Actions**, so `pages.yml`
has somewhere to deploy to.

## What they do

| File | Trigger | Purpose |
| --- | --- | --- |
| `ci.yml` | push, PR | Builds, asserts the committed `site/` matches `data/`, runs `tools/validate.py`. Source-link check runs separately as advisory. |
| `pages.yml` | push to `main` | Rebuilds, validates, deploys to GitHub Pages. Refuses to publish a page that fails validation. |
| `freshness.yml` | weekly (Mon 13:00 UTC) | Opens or updates a `stale-data` issue once `as_of` in `data/outbreak.json` ages past 21 days. |

Until `ci.yml` is active, run the checks locally before pushing:

```sh
python3 build.py && python3 tools/validate.py
```
