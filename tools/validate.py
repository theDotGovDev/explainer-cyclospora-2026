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
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pdf_text  # noqa: E402
from build import EVIDENCE, PROVENANCE, STATUS_LABEL, numeric_band  # noqa: E402
from icons import SPRITE_SYMBOLS  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"
PAGES = ["index.html", "methodology.html", "sources.html"]

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


def check_comparisons(comparisons, sources):
    """The comparison anchors were previously unvalidated entirely.

    They carry derived arithmetic and citations like everything else, so they
    need the same guarantees: real source ids, and a written-out derivation
    wherever we converted a published figure ourselves.
    """
    ids = {s["id"] for s in sources["sources"]}
    for key in ("basis_note", "caution"):
        if not comparisons.get(key):
            fail(f"comparisons.json is missing {key!r}")
    if not comparisons.get("anchors"):
        fail("comparisons.json has no anchors")
    for a in comparisons.get("anchors", []):
        who = a.get("label", "?")
        for field in ("odds", "label", "basis"):
            if not a.get(field):
                fail(f"comparison anchor {who!r} missing {field}")
        odds = a.get("odds")
        if isinstance(odds, (int, float)) and odds <= 1:
            fail(f"comparison anchor {who!r} has odds {odds}, which is not '1 in N'")
        # Anything we converted ourselves must show its working.
        if a.get("derived") and not a.get("derivation"):
            fail(f"comparison anchor {who!r} is marked derived but shows no "
                 f"arithmetic; add a 'derivation' or drop the flag")
        # Every anchor is either cited or self-evident arithmetic that says so.
        if not a.get("sources") and not a.get("note"):
            fail(f"comparison anchor {who!r} has neither a source nor a note "
                 f"explaining where the number comes from")
        for sid in a.get("sources", []):
            if sid not in ids:
                fail(f"comparison anchor {who!r} cites unknown source {sid!r}")


def check_history(outbreak, sources):
    """The append-only figure log must stay parseable and must not diverge.

    A history that quietly disagrees with the live page is worse than no
    history: it looks like a record and is not one.
    """
    path = DATA / "history.jsonl"
    if not path.exists():
        fail("data/history.jsonl is missing")
        return
    ids = {s["id"] for s in sources["sources"]}
    known_series = {"national_season", "iceberg_cluster"}
    records, seen = [], set()

    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as ex:
            fail(f"history.jsonl line {n}: not valid JSON ({ex})")
            continue
        records.append(r)
        for field in ("observed", "recorded", "series", "metrics", "sources"):
            if not r.get(field):
                fail(f"history.jsonl line {n}: missing {field}")
        if r.get("series") not in known_series:
            fail(f"history.jsonl line {n}: unknown series {r.get('series')!r}")
        for field in ("observed", "recorded"):
            try:
                datetime.date.fromisoformat(r.get(field, ""))
            except ValueError:
                fail(f"history.jsonl line {n}: {field} is not an ISO date")
        # (series, observed) may repeat: a revision of the same
        # observation date is legitimate and worth keeping. The
        # recorded date is what must make each line unique.
        key = (r.get("series"), r.get("observed"), r.get("recorded"))
        if key in seen:
            fail(f"history.jsonl line {n}: duplicate {key[0]} record for "
                 f"{key[1]} recorded {key[2]}")
        seen.add(key)
        for sid in r.get("sources", []):
            if sid not in ids:
                fail(f"history.jsonl line {n}: cites unknown source {sid!r}")
        if not isinstance(r.get("metrics"), dict) or not r["metrics"]:
            fail(f"history.jsonl line {n}: metrics must be a non-empty object")

    # The newest national_season entry must match what the site currently shows.
    ns = outbreak["national_season"]
    latest = [r for r in records if r.get("series") == "national_season"]
    if not latest:
        fail("history.jsonl has no national_season record")
        return
    newest = max(latest, key=lambda r: (r["observed"], r["recorded"]))
    if newest["observed"] != ns["as_of"]:
        fail(f"history.jsonl newest observation is {newest['observed']} but "
             f"outbreak.json reports as_of {ns['as_of']}; run tools/snapshot.py")
    for hk, ok_ in (("lab_confirmed", "lab_confirmed"),
                    ("probable", "probable_under_investigation"),
                    ("hospitalizations", "hospitalizations"),
                    ("deaths", "deaths")):
        if newest["metrics"].get(hk) != ns.get(ok_):
            fail(f"history.jsonl {hk}={newest['metrics'].get(hk)} disagrees with "
                 f"outbreak.json {ok_}={ns.get(ok_)}; run tools/snapshot.py")


def check_icons(foods):
    """Every icon name must exist in the sprite.

    A name that is not in the sprite renders as an empty <use> - silently, with
    no console error and no layout shift, so it is easy to ship. Three did.
    """
    for label, items in (("foods.json", foods["foods"]),):
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

        # Disclaimers are load-bearing. They must be on every page. Matched
        # on substance, not an exact sentence: an earlier version keyed on
        # the phrase 'cdc.gov or fda.gov' and broke the moment the wording
        # changed to 'and', which would have been a silent loss if the
        # check had been advisory.
        for needle, label in [
            ("not medical advice", "medical-advice disclaimer"),
            ("best-effort", "best-effort disclaimer"),
            ("not official statistics", "estimates-are-not-official disclaimer"),
            ("cdc.gov", "source-access limitation (CDC)"),
            ("fda.gov", "source-access limitation (FDA)"),
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


def check_evidence_labels(foods):
    """No food may render without a visible evidence label."""
    expected = {"index.html": len(foods["foods"]) * 2}  # card + table row
    for name, least in expected.items():
        path = SITE / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        found = len(re.findall(r'<a class="ev ev-', text))
        if found < least:
            fail(f"{name}: {found} evidence labels rendered, expected at least "
                 f"{least} - a food is rendering without one")


def check_label_links():
    """Every badge links to a definition, and every definition exists.

    Badges used to explain themselves with a title attribute, which is invisible
    on touch and cannot be linked to. They are links now, so a missing anchor
    would be a dead end on the most-clicked element on the site.
    """
    meth = (SITE / "methodology.html")
    if not meth.exists():
        fail("methodology.html missing, cannot verify label definitions")
        return
    ids = set(re.findall(r'id="((?:ev|status|prov)-[a-z0-9-]+)"',
                         meth.read_text(encoding="utf-8")))
    want = ({f"ev-{k}" for k in EVIDENCE} | {f"prov-{k}" for k in PROVENANCE}
            | {f"status-{k}" for k in STATUS_LABEL})
    for missing in sorted(want - ids):
        fail(f"label {missing!r} has no definition on methodology.html")
    for name in PAGES:
        path = SITE / name
        if not path.exists():
            continue
        for target in set(re.findall(
                r'href="methodology\.html#((?:ev|status|prov)-[a-z0-9-]+)"',
                path.read_text(encoding="utf-8"))):
            if target not in ids:
                fail(f"{name}: badge links to methodology.html#{target}, "
                     f"which does not exist")


def check_provenance():
    """Every citation must carry a sourcing marker, so no claim is unlabeled."""
    for name in PAGES:
        text = (SITE / name).read_text(encoding="utf-8")
        cites = len(re.findall(r'<sup class="cite">', text))
        # Legend/illustrative swatches carry data-sample and are not claims.
        marks = len(re.findall(r'<a class="prov prov-[a-z-]+"[^>]*?(?<!data-sample=")>', text))
        if cites and marks < cites:
            fail(f"{name}: {cites} citations but only {marks} sourcing markers")


# A Python call or name left in the output, e.g. "{glossary()}" or "{ns['deaths']}".
# Not a match for CSS or ordinary prose braces, which do not look like this.
STRAY_PLACEHOLDER = re.compile(r"\{[a-z_]+[a-z_0-9]*(\(\)|\[|\.)[^{}]*\}", re.I)


def check_placeholders():
    '''Catch an f-string that stopped being an f-string.

    Closing a page template's quotes to concatenate a call, then reopening
    them, silently ends the f-string: every placeholder after that point
    renders as literal text and the content it stood for disappears. That
    happened here. The whole label glossary dropped out of the methodology
    page, a literal {glossary()} took its place, and every existing check
    passed - the HTML was still well-formed, every citation still resolved,
    and no data file had changed.
    '''
    for name in PAGES:
        text = (SITE / name).read_text(encoding="utf-8")
        for m in STRAY_PLACEHOLDER.finditer(text):
            fail(f"{name}: uninterpolated template placeholder {m.group(0)!r} "
                 f"- an f-string was probably broken, and whatever it stood for "
                 f"is missing from the page")


def check_pdf_reader():
    """The PDF reader decides whether two cited figures can be checked at all.

    It runs offline against documents whose right answer is known, so it belongs
    with the other blocking checks rather than in the advisory link job.
    """
    for msg in pdf_text.selftest():
        fail(msg)


def main():
    outbreak = load("outbreak.json")
    foods = load("foods.json")
    sources = load("sources.json")
    comparisons = load("comparisons.json")

    check_data(outbreak, foods, sources)
    check_icons(foods)
    check_comparisons(comparisons, sources)
    check_history(outbreak, sources)
    check_dates(outbreak)
    check_html(outbreak)
    check_citations()
    check_provenance()
    check_label_links()
    check_evidence_labels(foods)
    check_placeholders()
    check_pdf_reader()

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
