#!/usr/bin/env python3
"""Validate the data files and the generated site.

Run after build.py. Exits non-zero on any failure so CI blocks the merge.

    python3 build.py && python3 tools/validate.py

The checks here exist because this site makes health claims. A broken citation
or a silently stale date is a correctness bug, not a cosmetic one.
"""

import datetime
import html.parser
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from build import EVIDENCE, numeric_band  # noqa: E402
from icons import SPRITE_SYMBOLS  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"
PAGES = ["index.html", "foods.html", "methodology.html", "sources.html"]

# How stale the outbreak data may get before CI complains.
STALE_AFTER_DAYS = 21

failures = []
warnings = []


def fail(msg):
    failures.append(msg)


def warn(msg):
    warnings.append(msg)


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- data checks

def check_data(outbreak, foods, sources):
    smap = {s["id"]: s for s in sources["sources"]}

    for s in sources["sources"]:
        for field in ("id", "tier", "publisher", "title", "url"):
            if not s.get(field):
                fail(f"source {s.get('id', '?')!r} missing {field}")
        if not str(s.get("url", "")).startswith("http"):
            fail(f"source {s['id']!r} has a non-http url")

    ids = [s["id"] for s in sources["sources"]]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        fail(f"duplicate source ids: {sorted(dupes)}")

    required = ("name", "detail", "status", "band", "risk_unmitigated",
                "mitigation", "risk_residual", "confidence", "sources")
    for f in foods["foods"]:
        for field in required:
            if not f.get(field):
                fail(f"food {f.get('name', '?')!r} missing {field}")
        if f.get("status") not in foods["status_legend"]:
            fail(f"food {f['name']!r} has unknown status {f.get('status')!r}")

        # The displayed band is derived from `scale`. The authored `band` is
        # kept as a statement of intent and must agree, so a mistyped range or
        # a mislabelled food is caught here rather than showing up as two
        # identically-placed bars in different colours on the chart.
        sc = f.get("scale") or {}
        if not sc.get("low") or not sc.get("high"):
            fail(f"food {f['name']!r} is missing scale.low / scale.high")
        elif sc["low"] > sc["high"]:
            fail(f"food {f['name']!r} has scale.low > scale.high")
        else:
            coarse = {"high": "high", "moderate": "moderate",
                      "low-moderate": "moderate", "low": "low",
                      "very-low": "very-low"}.get(f.get("band"))
            if coarse and coarse != numeric_band(sc):
                fail(f"food {f['name']!r} is authored as band {f['band']!r} but "
                     f"its range {sc['low']}-{sc['high']} computes to "
                     f"{numeric_band(sc)!r}")
        if not f.get("icon"):
            fail(f"food {f['name']!r} has no icon")

        # Every food must say how its risk claim is grounded, and anything
        # claiming a reference must actually carry one.
        ev = f.get("evidence")
        if ev not in EVIDENCE:
            fail(f"food {f['name']!r} has missing/unknown evidence basis {ev!r}")
        elif ev != "extrapolated" and not f.get("sources"):
            fail(f"food {f['name']!r} claims evidence {ev!r} but cites no source; "
                 f"either cite one or mark it 'extrapolated'")
        for sid in f.get("sources", []):
            if sid not in smap:
                fail(f"food {f['name']!r} cites unknown source {sid!r}")
        # Every risk claim must be hedged. These are estimates, not statistics.
        for field in ("risk_unmitigated", "risk_residual"):
            v = str(f.get(field, ""))
            if not re.search(r"~|below|negligible|to", v, re.I):
                fail(f"food {f['name']!r} states {field} as an unhedged "
                     f"point value: {v!r}")

    for c in outbreak.get("critical_caveats", []):
        for sid in c.get("sources", []):
            if sid not in smap:
                fail(f"caveat {c['title']!r} cites unknown source {sid!r}")

    # Determine what is actually cited from the rendered pages rather than from
    # the data files: some citations are written directly into the templates,
    # and scanning only the data would report those as uncited.
    cited = set()
    for name in PAGES:
        path = SITE / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        cited.update(re.findall(r'href="sources\.html#([^"]+)"', text))
        # A source linked directly by URL in prose counts as cited too.
        cited.update(sid for sid, s in smap.items() if s["url"] in text)
    for sid in sorted(set(smap) - cited):
        warn(f"source {sid!r} is listed but never cited on any page")


def check_top100(top100, sources):
    """The 100-food list is mostly extrapolation, so the labelling has to hold."""
    smap = {s["id"] for s in sources["sources"]}
    seen_ranks = set()
    for f in top100["foods"]:
        who = f.get("name", "?")
        if f.get("rank") in seen_ranks:
            fail(f"top100 {who!r} has duplicate rank {f.get('rank')}")
        seen_ranks.add(f.get("rank"))
        for field in ("name", "icon", "tier", "scale", "basis", "evidence"):
            if not f.get(field):
                fail(f"top100 {who!r} missing {field}")
        ev = f.get("evidence")
        if ev not in EVIDENCE:
            fail(f"top100 {who!r} has missing/unknown evidence basis {ev!r}")
        # Extrapolated entries still cite the pathogen behaviour they rest on,
        # so every food carries at least one source either way.
        if not f.get("sources"):
            fail(f"top100 {who!r} cites no source at all")
        for sid in f.get("sources", []):
            if sid not in smap:
                fail(f"top100 {who!r} cites unknown source {sid!r}")
    for name, v in top100.get("tiers", {}).items():
        if not v.get("sources"):
            fail(f"top100 tier {name!r} states a basis with no sources")
        for sid in v.get("sources", []):
            if sid not in smap:
                fail(f"top100 tier {name!r} cites unknown source {sid!r}")


def check_icons(foods, top100):
    """Every icon name must exist in the sprite.

    A name that is not in the sprite renders as an empty <use> - silently, with
    no console error and no layout shift, so it is easy to ship. Three did.
    """
    for label, items in (("foods.json", foods["foods"]),
                         ("top100.json", top100["foods"])):
        for f in items:
            if f.get("icon") and f["icon"] not in SPRITE_SYMBOLS:
                fail(f"{label}: {f['name']!r} uses icon {f['icon']!r}, which is "
                     f"not defined in the sprite")


def check_dates(outbreak):
    try:
        as_of = datetime.date.fromisoformat(outbreak["as_of"])
    except (KeyError, ValueError):
        fail("outbreak.json as_of is missing or not an ISO date")
        return
    today = datetime.date.today()
    if as_of > today:
        fail(f"outbreak.json as_of ({as_of}) is in the future")
    age = (today - as_of).days
    if age > STALE_AFTER_DAYS:
        fail(f"outbreak data is {age} days old (limit {STALE_AFTER_DAYS}). "
             f"Re-verify against CDC/FDA and bump as_of.")
    elif age > STALE_AFTER_DAYS // 2:
        warn(f"outbreak data is {age} days old and should be refreshed soon.")


# ---------------------------------------------------------------- html checks

class Nesting(html.parser.HTMLParser):
    VOID = {"meta", "link", "br", "hr", "img", "input", "source", "area", "col"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack:
            self.errors.append(f"stray </{tag}>")
        elif self.stack[-1] != tag:
            self.errors.append(f"expected </{self.stack[-1]}>, got </{tag}>")
        else:
            self.stack.pop()


def check_html(outbreak):
    for name in PAGES:
        path = SITE / name
        if not path.exists():
            fail(f"{name} was not generated")
            continue
        text = path.read_text(encoding="utf-8")

        p = Nesting()
        p.feed(text)
        for err in p.errors:
            fail(f"{name}: {err}")
        if p.stack:
            fail(f"{name}: unclosed tags {p.stack}")

        # Disclaimers are load-bearing. They must be on every page.
        for needle, label in [
            ("not medical advice", "medical-advice disclaimer"),
            ("best-effort", "best-effort disclaimer"),
            ("not official statistics", "estimates-are-not-official disclaimer"),
            ("cdc.gov or fda.gov", "source-access limitation"),
            ("generated using ai", "AI-generation disclosure"),
        ]:
            if needle.lower() not in text.lower():
                fail(f"{name}: missing {label} (looked for {needle!r})")

        if outbreak["as_of"] not in text:
            fail(f"{name}: does not carry the as_of date {outbreak['as_of']}")

        if "<title>" not in text or 'lang="en"' not in text:
            fail(f"{name}: missing <title> or lang attribute")

        # Every external link opens with rel=noopener.
        for m in re.finditer(r'<a href="(https?://[^"]+)"([^>]*)>', text):
            if "rel=" not in m.group(2):
                fail(f"{name}: external link without rel: {m.group(1)}")


def check_citations():
    """Inline [n] markers must agree with the numbering on sources.html."""
    src = (SITE / "sources.html").read_text(encoding="utf-8")
    numbering = dict(re.findall(r'<li id="([^"]+)" value="(\d+)"', src))
    if not numbering:
        fail("sources.html has no numbered entries")
    for name in PAGES:
        text = (SITE / name).read_text(encoding="utf-8")
        for sid, n in re.findall(
                r'href="sources\.html#([^"]+)"[^>]*>(\d+)</a>', text):
            if numbering.get(sid) != n:
                fail(f"{name}: citation [{n}] -> {sid} but sources.html "
                     f"numbers it [{numbering.get(sid)}]")


def check_evidence_labels(foods, top100):
    """No food may render without a visible evidence label."""
    expected = {
        "index.html": len(foods["foods"]) * 2,   # card + detailed table row
        "foods.html": len(top100["foods"]),
    }
    for name, least in expected.items():
        path = SITE / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        found = len(re.findall(r'<span class="ev ev-', text))
        if found < least:
            fail(f"{name}: {found} evidence labels rendered, expected at least "
                 f"{least} - a food is rendering without one")


def check_provenance():
    """Every citation must carry a sourcing marker, so no claim is unlabeled."""
    for name in PAGES:
        text = (SITE / name).read_text(encoding="utf-8")
        cites = len(re.findall(r'<sup class="cite">', text))
        # Legend/illustrative swatches carry data-sample and are not claims.
        marks = len(re.findall(r'<span class="prov prov-[a-z-]+"(?! data-sample)', text))
        if cites and marks < cites:
            fail(f"{name}: {cites} citations but only {marks} sourcing markers")


def main():
    outbreak = load("outbreak.json")
    foods = load("foods.json")
    sources = load("sources.json")
    top100 = load("top100.json")

    check_data(outbreak, foods, sources)
    check_top100(top100, sources)
    check_icons(foods, top100)
    check_dates(outbreak)
    check_html(outbreak)
    check_citations()
    check_provenance()
    check_evidence_labels(foods, top100)

    for w in warnings:
        print(f"warning: {w}")
    for f in failures:
        print(f"FAIL: {f}", file=sys.stderr)

    if failures:
        print(f"\n{len(failures)} check(s) failed.", file=sys.stderr)
        return 1
    print(f"all checks passed ({len(foods['foods'])} foods, "
          f"{len(sources['sources'])} sources, {len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
