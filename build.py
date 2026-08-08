#!/usr/bin/env python3
"""Render the static Cyclospora risk-assessment site from the JSON files in data/.

The JSON files under data/ are the canonical record. Edit those, re-run this
script, and commit the regenerated HTML. No third-party dependencies.

    python3 build.py
"""

import collections
import html
import json
import math
import pathlib

from icons import icon, logo, sprite

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
SITE = ROOT / "site"

BAND_LABEL = {
    "high": "Avoid",
    "moderate": "Caution",
    "low-moderate": "Caution",
    "low": "Low risk",
    "very-low": "Very low risk",
}

# Display collapses low-moderate into moderate: keeping them as separate hues
# would put amber beside orange, a pair the palette validator fails on the
# normal-vision floor, so that distinction lives in the text instead.
COARSE = {"high": "high", "moderate": "moderate", "low-moderate": "moderate",
          "low": "low", "very-low": "very-low"}

# Cut points on the geometric midpoint of a food's estimated range, in "1 in N".
BAND_CUTS = [(1e4, "high"), (10 ** 5.5, "moderate"), (10 ** 6.5, "low")]


def numeric_band(scale):
    """Derive the display band from the numbers rather than a hand-set field.

    Two foods with the same estimated range must land in the same band. When
    the band was authored by hand this drifted: fresh basil and cucumbers both
    sit at 1-in-50,000 to 1-in-500,000 but were labelled differently, which the
    chart rendered as two identically-placed bars in different colours.
    """
    mid = math.sqrt(scale["low"] * scale["high"])
    for cut, name in BAND_CUTS:
        if mid < cut:
            return name
    return "very-low"

STATUS_LABEL = {
    "confirmed": "Confirmed - implicated 2026",
    "under-traceback": "Under traceback",
    "linked-by-recall": "In recall scope",
    "historical": "Historical only",
    "not-implicated": "Not implicated",
}

STATUS_ICON = {
    "confirmed": "alert", "under-traceback": "search", "linked-by-recall": "bag",
    "historical": "info", "not-implicated": "check",
}


def e(text):
    return html.escape(str(text), quote=True)


def load(name):
    with open(DATA / name, encoding="utf-8") as fh:
        return json.load(fh)


def load_history():
    """Append-only figure log, oldest first. One JSON object per line."""
    path = DATA / "history.jsonl"
    if not path.exists():
        return []
    out = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()
           if ln.strip()]
    return sorted(out, key=lambda r: (r["series"], r["observed"], r["recorded"]))


TIERS = [
    ("primary", "Primary &mdash; government and public health agencies",
     "Authoritative. Where these differ from anything on this site, these are correct."),
    ("literature", "Peer-reviewed and surveillance literature",
     "Used for background epidemiology and burden multipliers."),
    ("expert", "Academic and expert commentary",
     "Used for interpretation, not for figures."),
    ("secondary", "News and consumer reporting",
     "Used chiefly to date events and to capture agency statements that could not be "
     "read directly. Treated as weaker than primary sources throughout."),
]


def ordered_sources(sources_doc):
    """Canonical citation order: grouped by tier, original order within a tier."""
    out = []
    for tier_id, _, _ in TIERS:
        out.extend(s for s in sources_doc["sources"] if s["tier"] == tier_id)
    known = {t[0] for t in TIERS}
    stray = [s["id"] for s in sources_doc["sources"] if s["tier"] not in known]
    if stray:
        raise SystemExit(f"sources with unknown tier (would be dropped): {stray}")
    return out


def source_map(sources_doc):
    smap = {s["id"]: s for s in sources_doc["sources"]}
    for i, s in enumerate(ordered_sources(sources_doc)):
        smap[s["id"]]["_n"] = i + 1
    return smap


PROVENANCE = {
    "agency": ("agency", "This claim rests on government, public health or "
                         "peer-reviewed sources."),
    "agency-news": ("agency + news", "This claim rests on a mix of agency sources "
                                     "and news reporting."),
    "news": ("news", "This claim rests only on news or consumer reporting. It has "
                     "not been confirmed against a primary agency document."),
}


def provenance(ids, smap):
    """Classify a claim by the strongest tier of source actually behind it."""
    tiers = {smap[i]["tier"] for i in ids if i in smap}
    if not tiers:
        return None
    strong = bool(tiers & {"primary", "literature"})
    weak = bool(tiers & {"secondary", "expert"})
    if strong and weak:
        return "agency-news"
    return "agency" if strong else "news"


def prov_tag(kind, sample=False):
    label, explain = PROVENANCE[kind]
    attr = ' data-sample="1"' if sample else ""
    return (f'<a class="prov prov-{e(kind)}" href="methodology.html#prov-{e(kind)}"{attr} '
            f'title="{e(explain)} Click for the full definition.">'
            f'<span class="vh">Sourcing: </span>{e(label)}</a>')


EVIDENCE = {
    "named-2026": ("named in 2026 sources", "referenced",
                   "This specific food is named in a 2026 outbreak source. The naming "
                   "is cited; the risk number is still our estimate."),
    "named-historical": ("named in past outbreaks", "referenced",
                         "Named in sources describing earlier U.S. outbreaks, not in "
                         "2026. The association is cited; the number is our estimate."),
    "general-guidance": ("covered by published guidance", "referenced",
                         "No source names this food as implicated, but published "
                         "guidance covers it directly. The guidance is cited; the "
                         "number is still our estimate."),
    "extrapolated": ("extrapolated - no source names this food", "extrapolated",
                     "No source names this food. Its risk is inferred by us from how "
                     "Cyclospora behaves and how the food is handled. This is the "
                     "weakest basis used on this site."),
}


def evidence_tag(kind, sample=False):
    """Say, for every food, whether a source names it or we extrapolated it.

    A citation can support 'this food was named in the outbreak' without
    supporting our per-serving number. Keeping the two separate stops a
    reference lending unearned authority to an estimate.

    Rendered as a link rather than a tooltip: a title attribute is invisible on
    touch devices and cannot be shared or pointed at.
    """
    if kind not in EVIDENCE:
        raise SystemExit(f"unknown evidence kind: {kind!r}")
    label, cls, explain = EVIDENCE[kind]
    attr = ' data-sample="1"' if sample else ""
    return (f'<a class="ev ev-{e(cls)}" href="methodology.html#ev-{e(kind)}"{attr} '
            f'title="{e(explain)} Click for the full definition.">'
            f'<span class="vh">Evidence basis: </span>{e(label)}</a>')


def status_tag(kind):
    """Outbreak status chip, linked to its definition."""
    return (f'<a class="status status-{e(kind)}" href="methodology.html#status-{e(kind)}" '
            f'title="{e(STATUS_DOC[kind][0])} Click for the full definition.">'
            f'{icon(STATUS_ICON[kind])}{e(STATUS_LABEL[kind])}</a>')


def cite(ids, smap, dated=None):
    """Render source ids as numbered links plus a provenance marker.

    Every citation is marked with where the claim actually came from, because a
    figure that reached us via a news article is not as good as one read off an
    agency page, and the reader should not have to chase links to tell which is
    which. `dated` stamps the claim with the date it describes.
    """
    if not ids:
        return ""
    links = []
    for sid in ids:
        src = smap.get(sid)
        if not src:
            # Fail loudly. Skipping silently makes a broken reference disappear
            # from the page rather than announce itself, which on a site whose
            # value is its citations is the worst possible failure mode.
            raise SystemExit(f"cite(): unknown source id {sid!r}")
        links.append(
            '<a href="sources.html#{sid}" title="{title} ({pub})">{num}</a>'.format(
                sid=e(sid), title=e(src["title"]), pub=e(src["publisher"]),
                num=src["_n"],
            )
        )
    if not links:
        return ""
    out = '<sup class="cite">[' + "][".join(links) + "]</sup>"
    kind = provenance(ids, smap)
    if kind:
        out += " " + prov_tag(kind)
    if dated:
        out += (' <span class="dated" title="The date this figure describes">'
                '<span class="vh">as of </span>'
                f'<time datetime="{e(dated)}">{e(dated)}</time></span>')
    return out


# --------------------------------------------------------------------------
# label glossary - every badge on the site links into this
# --------------------------------------------------------------------------

STATUS_DOC = {
    "confirmed": (
        "Named by FDA or CDC as implicated in the 2026 outbreak.",
        "Investigators interviewed people who got sick, found this food eaten far "
        "more often than expected, and traced the product back through distribution "
        "to a common supplier. That combination - epidemiology plus traceback - is "
        "what agencies act on, and it is what triggered the recall. It is worth "
        "knowing that no product sample in this outbreak has ever tested positive "
        "for Cyclospora: a border sample flagged positive was re-reviewed and "
        "reclassified as a false positive. The parasite is notoriously hard to "
        "detect in food, so a confirmed status here rests on where the illnesses "
        "point, not on a laboratory finding in the food itself."),
    "under-traceback": (
        "Investigators are actively tracing this food. It is not a conclusion.",
        "Traceback means following a product backwards through distributors, "
        "processors and growers to see whether the supply chains behind separate "
        "clusters of illness converge on one source. A food under traceback is a "
        "lead being checked, not a finding. Most commodities that enter traceback "
        "are eventually cleared, because early interviews pick up whatever people "
        "commonly eat. Treat this label as a reason for reasonable caution while "
        "the question is open, not as evidence the food made anyone ill."),
    "linked-by-recall": (
        "Not implicated on its own, but inside the recall's scope.",
        "The recall covers blended and prepared products that may contain the "
        "implicated ingredient, not only the single-ingredient product. A salad "
        "mix falls here if it can contain iceberg from the recalled supplier. The "
        "risk attaches to the ingredient, not to the category."),
    "historical": (
        "Associated with earlier U.S. outbreaks, but not with 2026.",
        "Cyclospora has a long U.S. outbreak record - imported raspberries in "
        "1996-97, snap peas in 2009, cilantro traced to Puebla in 2013-15, basil in "
        "2019 and 2020. A food carrying this label is not part of the current "
        "outbreak. The history matters because it shows the commodity can carry the "
        "parasite when growing or handling conditions go wrong, which is why these "
        "foods sit slightly above the ones with no such record."),
    "not-implicated": (
        "No association in 2026 and no strong outbreak history.",
        "Nothing in the current investigation points at this food, and it does not "
        "carry a meaningful record from past outbreaks. That is not the same as a "
        "guarantee. Traceback only sees the supply chains investigators look at, "
        "and an outbreak with no positive product sample cannot fully exclude "
        "commodities that were never sampled."),
}

PROVENANCE_DOC = {
    "agency": (
        "A government, public health or peer-reviewed source is behind this claim.",
        "The strongest sourcing used here. Note carefully what it does not mean: it "
        "says an agency originated the claim, not that we read it off the agency's "
        "own page. The build environment could not reach cdc.gov or fda.gov, so most "
        "agency figures on this site arrived by way of sources that cite them."),
    "agency-news": (
        "A mix of agency sources and news reporting.",
        "Typically an agency figure that reached us through reporting, with a news "
        "outlet supplying the date or the wording. Weaker than a claim resting on "
        "agency sources alone."),
    "news": (
        "News or consumer reporting only.",
        "No agency document supports this claim directly. These are the weakest "
        "claims on the site. They are still worth including - reporting often "
        "captures a state official's statement that never appears in a federal "
        "document - but they should carry the least weight."),
}

EVIDENCE_DOC = {
    "named-2026": (
        "A 2026 outbreak source names this specific food.",
        "An agency investigation, a recall notice, or a state health department "
        "statement identifies this food by name in the current outbreak. That is "
        "the strongest food-level evidence available here. It still does not mean "
        "an agency published a per-serving probability for it - none has, for any "
        "food. The naming is cited; the number remains our estimate."),
    "named-historical": (
        "Named in sources describing earlier U.S. outbreaks.",
        "This food is not implicated in 2026, but it appears by name in the record "
        "of past U.S. cyclosporiasis outbreaks. We treat that as real but weaker "
        "evidence: it shows the commodity can carry the parasite, not that it is "
        "carrying it now."),
    "general-guidance": (
        "Published guidance covers this food directly.",
        "No source names this food as implicated, but agency or expert guidance "
        "speaks to it - for example that it is considered safe with standard "
        "washing, or that cooking to temperature inactivates the parasite. The "
        "guidance is cited. The per-serving number is still ours."),
    "extrapolated": (
        "No source names this food. We worked the risk out ourselves.",
        "The weakest basis used anywhere on this site, and the one behind most of "
        "the 100-food list. We took what the sources establish about how Cyclospora "
        "behaves - that it is a fresh produce and water pathogen, that cooking to "
        "about 158 F inactivates it, that peeling removes surface contamination, "
        "that washing does not reliably work - and applied it to how the food is "
        "normally handled. The sources cited on an extrapolated food support that "
        "behaviour, not the food. If you are making a decision that matters, this "
        "is the label to be most sceptical of."),
}


def glossary():
    """The definitions every badge links to."""
    def block(prefix, doc, labels):
        out = []
        for key, (summary, detail) in doc.items():
            out.append(
                f'  <div class="gloss" id="{prefix}-{e(key)}">\n'
                f'    <h3>{labels[key]}</h3>\n'
                f'    <p class="gloss-sum">{e(summary)}</p>\n'
                f'    <p>{e(detail)}</p>\n'
                f'  </div>')
        return "\n".join(out)

    return f"""
<section class="glossary" aria-labelledby="labels-h">
  <h2 id="labels-h">What every label on this site means</h2>
  <p>Badges throughout the site link here. Each one answers a different question,
     and they are deliberately kept separate because they can disagree: a food can
     be named by an agency (strong evidence that it is implicated) while its risk
     number is still an estimate of ours (weak evidence for the number).</p>

  <h3 class="gloss-group">Outbreak status &mdash; what investigators have found about this food</h3>
{block("status", STATUS_DOC, {k: e(v) for k, v in STATUS_LABEL.items()})}

  <h3 class="gloss-group">Evidence basis &mdash; how our risk claim for this food is grounded</h3>
{block("ev", EVIDENCE_DOC, {k: e(v[0]) for k, v in EVIDENCE.items()})}

  <h3 class="gloss-group">Sourcing &mdash; where a given figure came from</h3>
{block("prov", PROVENANCE_DOC, {k: e(v[0]) for k, v in PROVENANCE.items()})}
</section>"""


# --------------------------------------------------------------------------
# shared chrome
# --------------------------------------------------------------------------

def page(title, description, body, active, as_of, subnav=None, extra_js=""):
    nav = [("index.html", "Risk by food"),
           ("methodology.html", "Methodology"),
           ("sources.html", "Sources")]
    nav_html = "\n".join(
        '        <a href="{href}"{cls}>{label}</a>'.format(
            href=href, label=e(label),
            cls=' class="active" aria-current="page"' if href == active else "",
        )
        for href, label in nav
    )
    sub = ""
    if subnav:
        links = "".join(f'<a href="#{e(a)}">{e(l)}</a>' for a, l in subnav)
        sub = (f'\n  <nav class="jump" aria-label="Sections on this page">'
               f'<div class="wrap jump-inner">'
               f'<span class="jump-label">On this page</span>{links}</div></nav>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<meta name="robots" content="index, follow">
<meta name="color-scheme" content="light dark">
<link rel="stylesheet" href="assets/style.css">
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
</head>
<body>
{sprite()}
<a class="skip" href="#main">Skip to content</a>

<div class="alert-bar" role="region" aria-label="Medical disclaimer">
  {icon('stethoscope', 'icon alert-icon')}
  <span><strong>Not medical advice.</strong> Independent, best-effort explainer.
  If you are ill, contact a clinician. In an emergency, call 911.</span>
</div>

<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="index.html">
      {logo()}
      <span class="brand-text">
        <span class="brand-name">Cyclospora Risk</span>
        <span class="brand-sub">2026 U.S. outbreak &middot; independent explainer</span>
      </span>
    </a>
    <nav class="site-nav" aria-label="Primary">
{nav_html}
    </nav>
  </div>{sub}
</header>

<div class="ai-note" role="note">
  <div class="wrap ai-note-inner">
    {icon('info', 'icon')}
    <p><strong>This page was generated using AI.</strong> The research, risk estimates and
       wording were produced by an AI system with human direction, and
       <strong>it may contain errors</strong> &mdash; including confidently-worded ones.
       The risk figures are our own estimates, not official statistics. Please read the
       <a href="methodology.html">methodology page</a> for how the numbers were derived,
       what they assume, and where the method is weak, and check anything that matters
       against the <a href="sources.html">primary sources</a>.</p>
  </div>
</div>

<main id="main">
{body}
</main>

<footer class="site-footer">
  <div class="wrap">
    <h2>{icon('info')} Disclaimers and limitations</h2>
    <ol class="disclaimers">
      <li><strong>This page was generated using AI, and may contain errors.</strong>
          The research, analysis, risk estimates and text were produced by an AI system
          working under human direction. AI systems can be wrong in ways that read as
          confident and well-sourced, including misreading a source, mis-stating a number,
          or citing something that does not support the claim. Everything here is traceable
          to the <a href="sources.html">sources page</a> and the
          <a href="methodology.html">methodology page</a> precisely so that you can check
          it rather than take it on trust. For anything that affects a real decision, verify
          against the primary agency sources.</li>
      <li><strong>This is not medical advice.</strong> Nothing here diagnoses, treats or
          prevents disease, and it is not a substitute for a licensed clinician. Cyclosporiasis
          is treated with prescription antibiotics; if you have watery diarrhea lasting more
          than a few days, seek care. Seek care urgently for signs of dehydration, bloody
          stool, high fever, or if you are immunocompromised, pregnant, very young or elderly.</li>
      <li><strong>The risk numbers are our estimates, not official statistics.</strong>
          No public health agency publishes per-serving risk for these foods. Every probability
          on this site was derived by this project using the method described on the
          <a href="methodology.html">methodology page</a>. They are order-of-magnitude
          approximations intended for relative comparison between foods. Do not cite them
          as agency figures.</li>
      <li><strong>Provided on a best-effort basis, without warranty.</strong> The information
          may be incomplete, outdated or wrong. No warranty of accuracy, completeness or
          fitness for any purpose is made or implied, and no liability is accepted for
          decisions made using it.</li>
      <li><strong>The case counts here come from news reporting, and are cited that way.</strong>
          They originate with CDC surveillance, but they reached this site through journalists
          reporting on it &mdash; cdc.gov and fda.gov both refuse automated requests, so nobody
          here has read those figures off an agency page. Rather than cite pages we have not
          read, we cite the reporting that actually carried each number, and link the agency
          pages separately as the place to verify. Treat the agencies as authoritative wherever
          they differ.</li>
      <li><strong>Published case counts disagree with one another.</strong> Counts vary by
          snapshot date and by whether they describe the full 2026 season or only the iceberg
          lettuce cluster. Where sources conflict we show the range rather than pick a number.</li>
      <li><strong>This is not the authoritative recall notice.</strong> For the definitive
          list of recalled products, lot codes and dates, use
          <a href="https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts" rel="noopener">FDA's
          recall announcements</a> and the recalling firm's own notice.</li>
      <li><strong>Individual risk varies substantially.</strong> These are population-average
          estimates. People who are immunocompromised, pregnant, elderly or very young face
          materially higher risk of severe illness, and both deaths in this outbreak were in
          people with significant underlying conditions. Geography matters too: risk was
          concentrated in the outbreak states.</li>
      <li><strong>Do not use this for clinical, regulatory, legal or commercial decisions.</strong>
          It is written for members of the public deciding what to eat.</li>
      <li><strong>No affiliation, and no agency branding.</strong> This site is not affiliated
          with, endorsed by, or connected to CDC, FDA, any state health department or any
          company. No agency logo appears here, deliberately: agency marks beside our own
          estimates would imply an endorsement that does not exist. Companies are named only
          because official sources named them, which is not an allegation of wrongdoing beyond
          what agencies have stated.</li>
      <li><strong>Do not read this as a reason to avoid fruits and vegetables.</strong> The
          health benefits of produce substantially outweigh these risks for nearly everyone.
          <a href="https://www.consumerreports.org/health/food-safety/you-shouldnt-avoid-fruits-and-vegetables-due-to-cyclospora-a9570579349/" rel="noopener">Consumer
          Reports</a> and food-safety experts have specifically cautioned against
          responding to this outbreak by cutting produce out of the diet. The purpose of this
          page is to help you substitute within produce, not away from it.</li>
    </ol>
    <p class="corrections">Found an error, or have a newer agency figure? Corrections are
       welcome via an issue or pull request on this repository. Every number here is traceable
       to an entry on the <a href="sources.html">sources page</a>.</p>
    <p class="built">Generated from <code>data/*.json</code> by <code>build.py</code>.
       Content current through {e(as_of)}.</p>
  </div>
</footer>
{extra_js}
</body>
</html>
"""


# --------------------------------------------------------------------------
# risk scale chart
# --------------------------------------------------------------------------

LOG_LO, LOG_HI = 2, 7  # 1-in-100 .. 1-in-10,000,000


def _pos(n):
    """Position a '1 in N' value. Higher risk (smaller N) sits further RIGHT.

    The axis is reversed relative to the raw log scale on purpose: readers
    expect worse to be further along, and the first version put the most
    dangerous food at the far left.
    """
    frac = (math.log10(n) - LOG_LO) / (LOG_HI - LOG_LO)
    return max(0.0, min(100.0, (1 - frac) * 100))


def risk_chart(foods):
    """Horizontal range plot of estimated per-serving risk, log scale.

    Sequential single-hue ramp: lightness carries magnitude, which survives
    colour-vision deficiency. A red/amber/green scale was measured and rejected
    - green against orange came out at deltaE 5.6 under protanopia, so the
    readers most in need of a risk scale could not have read it.
    """
    rows = sorted(foods, key=lambda f: math.sqrt(f["scale"]["low"] * f["scale"]["high"]))
    ticks = [(100, "1 in 100"), (1000, "1 in 1k"), (10_000, "1 in 10k"),
             (100_000, "1 in 100k"), (1_000_000, "1 in 1M"), (10_000_000, "1 in 10M")]
    # Ticks live in a row that shares the chart-row grid template, so they line
    # up with the bars and gridlines rather than with the figure's outer edge.
    # First and last are anchored inward so their labels are not clipped.
    tick_html = ""
    for v, lab in ticks:
        x = _pos(v)
        edge = " tick-first" if x < 1 else (" tick-last" if x > 99 else "")
        tick_html += (f'<span class="tick{edge}" style="left:{x:.2f}%">'
                      f'<span>{e(lab)}</span></span>')
    grid_html = "".join(
        f'<span class="grid-line" style="left:{_pos(v):.2f}%"></span>' for v, _ in ticks
    )

    bars = []
    for f in rows:
        lo, hi = f["scale"]["low"], f["scale"]["high"]
        # lo is the smaller denominator, so the higher risk, so further right.
        x_right, x_left = _pos(lo), _pos(hi)
        capped = lo == hi  # e.g. cooked vegetables, "below 1 in 10,000,000"
        if capped:
            # "Below 1 in N" continues off-scale to the left, so draw a stub at
            # the low-risk end that fades out leftward rather than a hard edge.
            x1, width = 0.0, 6.0
        else:
            x1, width = x_left, max(x_right - x_left, 1.2)
        band = numeric_band(f["scale"])
        label = (f"{f['name']}: estimated {f['risk_unmitigated']}. "
                 f"{BAND_LABEL[numeric_band(f['scale'])]}.")
        bars.append(f"""      <li class="chart-row chart-{e(band)}">
        <span class="chart-name">{icon(f['icon'], 'icon food-icon')}<span>{e(f['name'])}</span></span>
        <span class="chart-track" role="img" aria-label="{e(label)}">
          {grid_html}
          <span class="chart-bar{' chart-capped' if capped else ''}"
                style="left:{x1:.2f}%;width:{width:.2f}%"></span>
        </span>
        <span class="chart-value">{e(f['risk_unmitigated'].split(';')[0])}</span>
      </li>""")

    # Ordered low -> high so the legend reads in the same direction as the axis.
    legend = "".join(
        f'<span class="chart-key chart-{e(k)}"><i></i>{e(v)}</span>'
        for k, v in [("very-low", "Very low risk"), ("low", "Low risk"),
                     ("moderate", "Caution"), ("high", "Avoid")]
    )

    return f"""<figure class="chart">
  <figcaption>
    <strong>Estimated risk per serving, before mitigation.</strong>
    Further right means higher risk, and darker means higher risk &mdash; the two
    say the same thing. The scale is logarithmic: each gridline is ten times more
    likely than the one to its left. Bars show the estimated range, not a
    precise value.
  </figcaption>
  <div class="chart-legend">{legend}</div>
  <div class="chart-plot">
    <ol class="chart-rows">
{chr(10).join(bars)}
    </ol>
    <div class="chart-axis-row">
      <span></span>
      <div class="chart-axis">{tick_html}</div>
      <span></span>
    </div>
  </div>
  <p class="chart-foot">These are informed estimates produced by this project, not
     official statistics. They are reliable for ranking foods against each other and
     unreliable as absolute probabilities.
     <a href="methodology.html">See how they were calculated</a>.</p>
</figure>"""


# --------------------------------------------------------------------------
# making "1 in N" mean something
# --------------------------------------------------------------------------

GRID_N = 1000


def dot_grid(foods):
    """A literal 1-in-1,000 grid, then every food expressed in the same terms.

    Abstract odds become countable. Each food says how many grids like this one
    you would have to fill before expecting a single case - which puts all of
    them on one concrete scale instead of a wall of "1 in N".
    """
    dots = "".join(
        f'<span class="dot{" dot-on" if i == 436 else ""}"></span>'
        for i in range(GRID_N)
    )
    rows = []
    for f in sorted(foods, key=lambda x: math.sqrt(x["scale"]["low"] * x["scale"]["high"])):
        lo, hi = f["scale"]["low"], f["scale"]["high"]
        mid = math.sqrt(lo * hi)
        grids = mid / GRID_N
        if grids < 1:
            # Riskier than the reference grid: more than one dot lights up in it.
            howmany = f"{GRID_N / mid:.1f} dots in this one grid"
        elif f["scale"]["low"] == f["scale"]["high"]:
            howmany = f"{grids:,.0f}+ grids"
        else:
            howmany = f"{grids:,.0f} grids"
        band = numeric_band(f["scale"])
        rows.append(f"""      <li class="dotrow">
        <span class="dotrow-name">{icon(f['icon'], 'icon food-icon')}{e(f['name'])}</span>
        <span class="band band-{e(band)}">{e(BAND_LABEL[band])}</span>
        <span class="dotrow-count">{e(howmany)}</span>
      </li>""")

    return f"""<figure class="dotfig">
  <figcaption><strong>This is what 1 in 1,000 looks like.</strong> Every dot is one
    person eating one serving. One of them &mdash; the dark one &mdash; gets sick.</figcaption>
  <div class="dots" role="img"
       aria-label="A grid of 1,000 dots with a single dot highlighted, illustrating odds of 1 in 1,000.">{dots}</div>

  <h3 class="dot-h">Every food on this page, in grids</h3>
  <p class="dot-lede">How many grids like the one above you would need to fill before
     expecting a single case of illness. <strong>More grids means safer.</strong>
     Where a food is riskier than the reference grid, more than one dot lights up
     inside it instead.</p>
  <ol class="dotrows">
{chr(10).join(rows)}
  </ol>
</figure>"""


LADDER_LO, LADDER_HI = 0, 9  # 1-in-1 .. 1-in-1,000,000,000


def _lpos(n):
    """Same convention as the risk chart: more likely sits further RIGHT."""
    frac = (math.log10(n) - LADDER_LO) / (LADDER_HI - LADDER_LO)
    return max(0.0, min(100.0, (1 - frac) * 100))


def ladder_ticks():
    out = []
    for i in range(10):
        if i % 3 and i != 9:
            continue
        x = _lpos(10 ** i)
        edge = " tick-first" if x < 1 else (" tick-last" if x > 99 else "")
        out.append(f'<span class="tick{edge}" style="left:{x:.2f}%">'
                   f'<span>1 in {10 ** i:,}</span></span>')
    return "".join(out)


def comparison_ladder(comparisons, foods, smap):
    """Foods and real-world anchors, all on ONE basis: a single occasion.

    Per-serving is the unit the whole site uses, so the anchors are converted to
    per-event rather than the food risks being converted to per-year. Published
    odds are usually quoted per year or per lifetime; each conversion below shows
    its arithmetic so it can be checked rather than taken on trust.
    """
    items = []
    for a in comparisons["anchors"]:
        items.append({
            "odds": a["odds"], "label": a["label"], "kind": "anchor",
            "sub": a["basis"] + (" &middot; converted by us" if a.get("derived") else ""),
            "sources": a.get("sources", []),
            "derivation": a.get("derivation"), "note": a.get("note"),
        })
    for f in foods:
        lo, hi = f["scale"]["low"], f["scale"]["high"]
        items.append({
            "odds": math.sqrt(lo * hi), "label": f["name"], "kind": "food",
            "band": numeric_band(f["scale"]), "capped": lo == hi,
            "sub": "per serving" + (" &middot; withdrawn from sale"
                                    if f.get("withdrawn") else ""),
            "sources": [], "derivation": None, "note": None,
        })

    rows, notes = [], []
    for it in sorted(items, key=lambda x: -x["odds"]):
        cls = ("ladder-anchor" if it["kind"] == "anchor"
               else f"ladder-food band-{it['band']}")
        odds_s = ("below 1 in " if it.get("capped") else "1 in ") + f"{it['odds']:,.0f}"
        rows.append(f"""      <li class="ladder-row {cls}">
        <span class="ladder-label">{e(it['label'])}
          <span class="ladder-basis">{it['sub']}</span></span>
        <span class="ladder-track">
          <span class="ladder-dot" style="left:{_lpos(max(it['odds'], 1.0)):.2f}%"></span>
        </span>
        <span class="ladder-odds">{e(odds_s)}{cite(it['sources'], smap)}</span>
      </li>""")
        if it["derivation"] or it["note"]:
            body = " ".join(x for x in (it["note"], it["derivation"]) if x)
            notes.append(f'  <details class="ladder-work">\n'
                         f'    <summary>{e(it["label"])} &mdash; {e(it["sub"].replace("&middot;", "-"))}</summary>\n'
                         f'    <p>{e(body)}{cite(it["sources"], smap)}</p>\n'
                         f'  </details>')

    return f"""<figure class="ladder">
  <figcaption><strong>Everything from one single occasion.</strong>
    One serving, one trip, one meal, one hand, one ticket, one day.
    Further right means more likely.</figcaption>
  <div class="ladder-warn" role="note">
    {icon('info')}
    <p><strong>Why these are comparable, and where they are not.</strong>
       {e(comparisons['basis_note'])} {e(comparisons['caution'])}</p>
  </div>
  <div class="ladder-plot">
    <ol class="ladder-rows">
{chr(10).join(rows)}
    </ol>
    <div class="ladder-axis-row">
      <span></span>
      <div class="ladder-axis">{ladder_ticks()}</div>
      <span></span>
    </div>
  </div>
  <h3 class="ladder-h">Where each anchor comes from</h3>
  <p class="dot-lede">Anchors marked &ldquo;converted by us&rdquo; were not published in
     per-occasion form; those entries show the full arithmetic so you can check it.
     The rest show their source.</p>
{chr(10).join(notes)}
</figure>"""


SERIES_LABEL = {
    "national_season": "All U.S. cases since May 1, 2026",
    "iceberg_cluster": "The iceberg lettuce cluster only",
}

METRIC_LABEL = {
    "lab_confirmed": "Lab-confirmed", "probable": "Probable", "cases": "Cases",
    "hospitalizations": "Hospitalised", "deaths": "Deaths", "states": "States",
}


def history_table(history, smap):
    """Show how the published figures have moved, rather than only the latest.

    The site otherwise displays one snapshot and silently discards every earlier
    one, which on a set of numbers that has already been revised more than once
    hides exactly the thing a careful reader wants to see.
    """
    if not history:
        return ""
    blocks = []
    for series in ("national_season", "iceberg_cluster"):
        rows = [r for r in history if r["series"] == series]
        if not rows:
            continue
        cols = []
        for r in rows:
            for k in r["metrics"]:
                if k not in cols:
                    cols.append(k)
        head = "".join(f"<th scope=\"col\">{e(METRIC_LABEL.get(c, c))}</th>" for c in cols)
        body = []
        for r in rows:
            cells = "".join(
                f'<td>{r["metrics"][c]:,}</td>' if isinstance(r["metrics"].get(c), int)
                else "<td class=\"nodata\">&mdash;</td>" for c in cols)
            seen_before = sum(1 for x in rows if x["observed"] == r["observed"])
            rev = ('<span class="hist-rev">revised</span>'
                   if seen_before > 1 and r is not next(
                       x for x in rows if x["observed"] == r["observed"]) else "")
            body.append(
                f'        <tr><th scope="row"><time datetime="{e(r["observed"])}">'
                f'{e(r["observed"])}</time>{rev}</th>{cells}'
                f'<td class="hist-src">{cite(r.get("sources"), smap)}</td></tr>')
        note = next((r.get("note") for r in reversed(rows) if r.get("note")), "")
        blocks.append(f"""    <h3>{e(SERIES_LABEL[series])}</h3>
    <div class="table-scroll">
    <table class="risk-table hist-table">
      <thead><tr><th scope="col">As of</th>{head}<th scope="col">Sources</th></tr></thead>
      <tbody>
{chr(10).join(body)}
      </tbody>
    </table>
    </div>
    {'<p class="hist-note">' + e(note) + '</p>' if note else ''}""")

    return f"""
<section id="history" class="band-section alt" aria-labelledby="history-h">
  <div class="wrap">
    <h2 id="history-h">How these figures have changed</h2>
    <p class="section-intro">Outbreak counts get revised, and a page that only ever
       shows the newest number hides that. Every figure this site has published is kept
       in an append-only log, so you can see what moved and when.</p>
{chr(10).join(blocks)}
    <p class="hist-foot">{icon('info')} The log is
       <code>data/history.jsonl</code> in the repository &mdash; one JSON record per line,
       appended and never rewritten. It starts when the log was created, so earlier
       figures appear only where a defensible date could be attached to them. The counts
       are not directly comparable across the two tables: one covers all U.S. cases this
       season, the other only the iceberg lettuce cluster.</p>
  </div>
</section>"""


# --------------------------------------------------------------------------
# index
# --------------------------------------------------------------------------

def food_cards(foods, smap):
    cards = []
    for f in foods:
        band = numeric_band(f["scale"])
        haystack = f"{f['name']} {f['detail']}".lower()
        cards.append(f"""      <article class="card card-{e(band)}" data-name="{e(haystack)}"
               data-band="{e(band)}">
        <header class="card-head">
          <span class="card-icon">{icon(f['icon'])}</span>
          <h3>{e(f['name'])}</h3>
          <span class="band band-{e(band)}">{e(BAND_LABEL[band])}</span>
        </header>
        <dl class="card-body">
          <dt>Estimated risk per serving</dt>
          <dd class="card-risk">{e(f['risk_unmitigated'])}</dd>
          <dt>{icon('check')} What to do</dt>
          <dd>{e(f['mitigation'])}</dd>
          <dt>Risk after doing that</dt>
          <dd class="card-risk">{e(f['risk_residual'])}</dd>
        </dl>
        <footer class="card-foot">
          {status_tag(f['status'])}
          {evidence_tag(f['evidence'])}
          <details class="card-more">
            <summary>Why, and how sure we are</summary>
            <p>{e(f['detail'])}{cite(f.get('sources'), smap)}</p>
            {'<p class="residual-note">' + e(f['residual_note']) + '</p>' if f.get('residual_note') else ''}
            <p class="conf">Confidence in this estimate:
               <strong>{e(f['confidence'].replace('-', ' to '))}</strong></p>
          </details>
        </footer>
      </article>""")
    return "\n".join(cards)


def build_index(outbreak, foods, comparisons, history, smap):
    ns = outbreak["national_season"]
    io = outbreak["implicated_outbreak"]
    rc = outbreak["recall"]
    bio = outbreak["biology"]
    flist = foods["foods"]

    rows = []
    for f in flist:
        rows.append(f"""      <tr class="band-{e(numeric_band(f['scale']))}">
        <th scope="row">
          <span class="food-name">{icon(f['icon'], 'icon food-icon')}{e(f['name'])}</span>
          <span class="food-detail">{e(f['detail'])}{cite(f.get('sources'), smap)}</span>
          <span class="food-ev">{evidence_tag(f['evidence'])}</span>
        </th>
        <td data-label="Status">{status_tag(f['status'])}</td>
        <td data-label="Estimated risk per serving"><span class="band band-{e(numeric_band(f['scale']))}">{e(BAND_LABEL[numeric_band(f['scale'])])}</span>
            <span class="risk">{e(f['risk_unmitigated'])}</span></td>
        <td data-label="Primary mitigation">{e(f['mitigation'])}</td>
        <td data-label="Residual risk after mitigation"><span class="risk">{e(f['risk_residual'])}</span>
            {'<span class="residual-note">' + e(f['residual_note']) + '</span>' if f.get('residual_note') else ''}</td>
        <td data-label="Confidence"><span class="conf conf-{e(f['confidence'])}">{e(f['confidence'].replace('-', ' to '))}</span></td>
      </tr>""")

    caveats = "\n".join(
        f"""    <details class="caveat">
      <summary>{icon('alert')}{e(c['title'])}</summary>
      <p>{e(c['body'])}{cite(c.get('sources'), smap)}</p>
    </details>"""
        for c in outbreak["critical_caveats"]
    )

    body = f"""
<section class="hero" aria-labelledby="hero-h">
  <div class="wrap">
    <p class="eyebrow">{icon('alert')} Active outbreak &middot; updated {e(outbreak['as_of'])}</p>
    <h1 id="hero-h">Is it safe to eat?</h1>
    <p class="hero-lede">Practical, source-cited risk estimates for the 2026 U.S.
       <em>Cyclospora</em> outbreak &mdash; food by food, with what actually reduces
       the risk and by how much.</p>
    <div class="hero-answer">
      <p><strong>The short version:</strong> one recalled product drove this outbreak
         &mdash; iceberg lettuce from Taylor Farms de Mexico, pulled from the market on
         {e(rc['date'])}. If you are not eating recalled product, your risk from any
         single food below is well under 1 in 10,000. <strong>Washing does not work on
         this parasite.</strong> Cooking and peeling do.</p>
    </div>
    <div class="hero-actions">
      <a class="btn btn-primary" href="#check">{icon('search')} Check a food</a>
      <a class="btn" href="#works">{icon('flame')} What actually works</a>
      <a class="btn" href="#care">{icon('stethoscope')} When to seek care</a>
    </div>
  </div>
</section>

<section id="check" class="band-section" aria-labelledby="check-h">
  <div class="wrap">
    <h2 id="check-h">{icon('search')} Check a food</h2>
    <p class="section-intro">Search or filter to find what you are about to eat.
       Every card shows the estimated risk, the one thing worth doing about it, and
       the risk remaining afterwards.</p>

    <div class="filters">
      <div class="search-wrap">
        {icon('search', 'icon search-icon')}
        <label class="vh" for="food-search">Search foods</label>
        <input type="search" id="food-search" placeholder="Search: lettuce, cilantro, berries&hellip;"
               autocomplete="off">
      </div>
      <div class="chips" role="group" aria-label="Filter by risk level">
        <button type="button" class="chip is-on" data-filter="all">All 16</button>
        <button type="button" class="chip chip-high" data-filter="high">Avoid</button>
        <button type="button" class="chip chip-moderate" data-filter="moderate">Caution</button>
        <button type="button" class="chip chip-low" data-filter="low">Low risk</button>
        <button type="button" class="chip chip-very-low" data-filter="very-low">Very low</button>
      </div>
    </div>
    <p class="filter-status" id="filter-status" role="status"></p>

    <div class="cards" id="cards">
{food_cards(flist, smap)}
    </div>
    <p class="no-results" id="no-results" hidden>No foods match that search.
       <button type="button" class="linklike" data-filter="all">Show all 16</button></p>
  </div>
</section>

<section id="scale" class="band-section alt" aria-labelledby="scale-h">
  <div class="wrap">
    <h2 id="scale-h">Everything on one scale</h2>
    <p class="section-intro">The same estimates, ordered from most to least risky, so
       you can see how far apart they actually are.</p>
{risk_chart(flist)}
  </div>
</section>

<section id="sense" class="band-section" aria-labelledby="sense-h">
  <div class="wrap">
    <h2 id="sense-h">What does "1 in 100,000" actually mean?</h2>
    <p class="section-intro">Risk numbers this small are hard to feel. Two ways to get a
       grip on them &mdash; one by counting, one by comparison.</p>
{dot_grid(flist)}
{comparison_ladder(comparisons, flist, smap)}
  </div>
</section>

{history_table(history, smap)}

<section id="works" class="band-section" aria-labelledby="works-h">
  <div class="wrap">
    <h2 id="works-h">{icon('flame')} What actually works</h2>
    <p class="section-intro">Cyclospora does not behave like the bacteria most food-safety
       advice is written for. Two things work well, one thing barely works at all.</p>
    <div class="works-grid">
      <div class="work work-yes">
        <span class="work-icon">{icon('flame')}</span>
        <h3>Cooking <span class="work-verdict">Works</span></h3>
        <p>{e(bio['cooking'])}</p>
      </div>
      <div class="work work-yes">
        <span class="work-icon">{icon('peel')}</span>
        <h3>Peeling <span class="work-verdict">Works</span></h3>
        <p>{e(bio['peeling'])}</p>
      </div>
      <div class="work work-yes">
        <span class="work-icon">{icon('ban')}</span>
        <h3>Avoiding recalled product <span class="work-verdict">Works</span></h3>
        <p>Removing the implicated supply is the single largest effect available, because
           it removes exposure entirely rather than reducing the dose. Check products
           against current FDA recall listings.</p>
      </div>
      <div class="work work-no">
        <span class="work-icon">{icon('droplet')}</span>
        <h3>Washing <span class="work-verdict work-verdict-no">Barely helps</span></h3>
        <p>{e(bio['washing'])}</p>
      </div>
    </div>
    <p class="works-foot">{icon('info')} Cyclospora also does not spread person-to-person in
       any meaningful way. {e(bio['person_to_person'])}{cite(bio.get('sources'), smap)}</p>
  </div>
</section>

<section id="status" class="band-section alt" aria-labelledby="status-h">
  <div class="wrap">
    <h2 id="status-h">Where the outbreak stands</h2>
    <div class="stats">
      <div class="stat">
        <span class="stat-num">{ns['lab_confirmed']:,}</span>
        <span class="stat-label">lab-confirmed cases since May&nbsp;1, 2026</span>
      </div>
      <div class="stat">
        <span class="stat-num">{ns['probable_under_investigation']:,}</span>
        <span class="stat-label">further probable cases under investigation</span>
      </div>
      <div class="stat">
        <span class="stat-num">{ns['hospitalizations']:,}</span>
        <span class="stat-label">hospitalizations</span>
      </div>
      <div class="stat stat-grave">
        <span class="stat-num">{ns['deaths']}</span>
        <span class="stat-label">deaths</span>
      </div>
    </div>
    <p class="stat-foot">{e(ns['window'])}, as of {e(ns['as_of'])}. {e(ns['states_with_cases'])}
       {e(ns['deaths_note'])}{cite(ns['sources'], smap, ns['as_of'])}</p>
    <p class="attrib-note">{icon('info')} <strong>Why these cite news outlets, not CDC.</strong>
       {e(ns['attribution_note'])}
       <a href="methodology.html#m5">More on where the numbers come from</a>.</p>

    <h3>The implicated supply chain</h3>
    <dl class="facts">
      <dt>Vehicle</dt><dd>{e(io['vehicle'])}{cite(io.get('sources'), smap)}</dd>
      <dt>Supplier</dt><dd>{e(io['supplier'])}</dd>
      <dt>How it surfaced</dt><dd>{e(io['first_announced_detail'])} ({e(io['first_announced'])})</dd>
      <dt>Scope since</dt><dd>{e(io['expansion_detail'])}</dd>
      <dt>Illness onsets</dt><dd>{e(io['onset_range'])}</dd>
      <dt>Evidence basis</dt><dd>{e(io['evidence_basis'])}</dd>
      <dt>Recall</dt><dd>{e(rc['scope'])} {e(rc['distribution'])} {e(rc['blends_note'])}{cite(rc.get('sources'), smap, rc['date'])}</dd>
      <dt>Recalled retail products</dt><dd>{e(rc['retail_products'])}{cite(['fda-recall', 'cnn-safe-food'], smap, rc['date'])}</dd>
    </dl>
  </div>
</section>

<section id="evidence" class="band-section" aria-labelledby="evidence-h">
  <div class="wrap">
    <h2 id="evidence-h">What the evidence does and does not show</h2>
    <p class="section-intro">Separating confirmed findings from open questions and from
       historical associations is the most decision-relevant part of this page. Expand any
       item to read it in full.</p>
{caveats}

    <div class="prov-key">
      <h3>How to read the evidence labels on each food</h3>
      <p>Every food carries a label saying whether a source names it or whether we
         extrapolated it from how the parasite behaves:</p>
      <ul class="evkey-list">
        <li>{evidence_tag('named-2026', sample=True)} A 2026 outbreak source names this food.</li>
        <li>{evidence_tag('named-historical', sample=True)} Named in earlier U.S. outbreaks.</li>
        <li>{evidence_tag('general-guidance', sample=True)} Published guidance covers it directly.</li>
        <li>{evidence_tag('extrapolated', sample=True)} No source names it. Inferred by us &mdash; the
            weakest basis on this site.</li>
      </ul>
      <p><strong>The risk number is always our estimate</strong>, whichever label a food
         carries. No agency publishes per-serving probabilities for foods.</p>

      <h3>How to read the sourcing markers</h3>
      <p>Every figure is tagged with where it came from and, where it moves, the date it
         describes. Nothing here is presented as fact without showing what is behind it.</p>
      <ul class="prov-legend">
        <li>{prov_tag('agency', sample=True)} Backed by a government, public health or
            peer-reviewed source.</li>
        <li>{prov_tag('agency-news', sample=True)} Backed by a mix of agency sources and
            news reporting.</li>
        <li>{prov_tag('news', sample=True)} Backed only by news or consumer reporting, and
            not confirmed against a primary agency document. The weakest claims here.</li>
        <li><span class="dated"><time datetime="{e(ns['as_of'])}">{e(ns['as_of'])}</time></span>
            The date the figure describes &mdash; not the date you are reading it.</li>
      </ul>
      <p class="prov-caveat">{icon('alert')} <strong>Important:</strong> an
         {prov_tag('agency', sample=True)} marker means an agency is the origin of the claim,
         not that we read it off the agency's own page. As explained in the
         <a href="methodology.html#m5">methodology</a>, cdc.gov and fda.gov were unreachable
         from the build environment, so most agency figures here arrived by way of sources
         that cite them.</p>
    </div>
  </div>
</section>

<section id="table" class="band-section alt" aria-labelledby="table-h">
  <div class="wrap">
    <h2 id="table-h">Full comparison table</h2>
    <p class="section-intro">{e(foods['risk_basis'])}</p>
    <details class="table-toggle">
      <summary>Show the full table for all 16 foods</summary>
      <div class="table-scroll">
      <table class="risk-table">
        <caption>Estimated per-serving risk of Cyclospora infection, United States,
          current outbreak window</caption>
        <thead>
          <tr>
            <th scope="col">Food</th>
            <th scope="col">2026 status</th>
            <th scope="col">Est. risk per serving<br><span class="th-sub">before mitigation</span></th>
            <th scope="col">Primary mitigation</th>
            <th scope="col">Est. residual risk<br><span class="th-sub">after mitigation</span></th>
            <th scope="col">Confidence</th>
          </tr>
        </thead>
        <tbody>
{chr(10).join(rows)}
        </tbody>
      </table>
      </div>
    </details>

    <h3>What the status labels mean</h3>
    <ul class="legend">
{chr(10).join(f'      <li>{status_tag(k)} {e(v)}</li>' for k, v in foods["status_legend"].items())}
    </ul>
  </div>
</section>

<section id="care" class="band-section care" aria-labelledby="care-h">
  <div class="wrap">
    <h2 id="care-h">{icon('stethoscope')} When to seek care</h2>
    <p>Cyclosporiasis does not reliably resolve on its own and is treated with prescription
       antibiotics, so it is worth getting diagnosed rather than waiting it out. Standard stool
       tests do not always look for Cyclospora &mdash; it often needs a specific request or a
       multiplex GI panel, so mention recent produce exposure to your clinician.</p>
    <div class="care-grid">
      <div class="care-box">
        <h3>{icon('alert')} Seek care promptly</h3>
        <ul>
          <li>Watery diarrhea lasting more than a few days</li>
          <li>Diarrhea that improves, then relapses</li>
          <li>Signs of dehydration &mdash; dizziness standing up, little or no urination</li>
          <li>Fever alongside diarrhea</li>
          <li>Any diarrheal illness if you are immunocompromised, pregnant, elderly,
              or caring for a young child</li>
        </ul>
      </div>
      <div class="care-box care-urgent">
        <h3>{icon('cross')} Call 911</h3>
        <ul>
          <li>Severe dehydration</li>
          <li>Fainting or collapse</li>
          <li>Bloody stool</li>
        </ul>
      </div>
    </div>
    <p class="care-note">{e(bio['incubation'])} This section describes when to consult a
       professional. It is not a diagnosis and not medical advice.</p>
  </div>
</section>
"""
    subnav = [("check", "Check a food"), ("scale", "Risk scale"),
              ("sense", "What the odds mean"), ("history", "How figures changed"),
              ("works", "What works"), ("status", "Outbreak"),
              ("evidence", "Evidence"), ("care", "Seek care")]
    js = '<script src="assets/app.js" defer></script>'
    return page(
        "Is it safe to eat? U.S. Cyclospora outbreak risk by food",
        "Actionable, source-cited risk assessment for the 2026 U.S. Cyclospora "
        "outbreak, with per-serving estimates and mitigations by food.",
        body, "index.html", outbreak["as_of"], subnav=subnav, extra_js=js,
    )


# --------------------------------------------------------------------------
# methodology
# --------------------------------------------------------------------------

def build_methodology(outbreak, smap):
    ns = outbreak["national_season"]
    body = f"""
<div class="wrap page-body">
<h1>Methodology</h1>
<p class="page-lede">How the per-serving risk estimates were calculated, what they
   assume, and where the method is weak.</p>

<section class="ai-section" aria-labelledby="m0">
  <h2 id="m0">How this site was made, and what that means for trusting it</h2>
  <p><strong>This site was generated using AI.</strong> An AI system did the research,
     built the risk model, wrote the text and produced the code, working under human
     direction. That is worth stating plainly at the top of the methodology rather than
     in small print, because it should change how you read everything else here.</p>
  <h3>What that means in practice</h3>
  <ul>
    <li><strong>Errors are possible and will not look like errors.</strong> AI systems
        produce fluent, confident, well-formatted text whether or not the underlying facts
        are right. A wrong number here will look exactly like a right one.</li>
    <li><strong>The specific failure modes worth watching for</strong> are a misread source,
        a number transcribed from the wrong row or the wrong date, a citation attached to a
        claim it does not actually support, and a plausible-sounding inference presented
        with more confidence than the evidence carries.</li>
    <li><strong>Everything is designed to be checkable.</strong> Every claim carries a
        numbered source and a marker showing whether it came from an agency or from news
        reporting. The calculation is written out step by step below, including its
        weaknesses. That structure exists so you can audit the work rather than trust it.</li>
    <li><strong>No clinician or epidemiologist has reviewed this.</strong> It has not been
        through professional or peer review.</li>
  </ul>
  <p>If you find an error, an issue or pull request on the repository is welcome and will
     be acted on.</p>
</section>

<section aria-labelledby="m1">
  <h2 id="m1">What these numbers are</h2>
  <p>No agency publishes the probability of getting sick from one serving of a given food.
     The risk figures on this site are <strong>informed estimates produced by this project</strong>,
     built from published case counts, published consumption data, and stated assumptions.
     They are rounded aggressively &mdash; to the nearest order of magnitude &mdash; because
     the underlying uncertainty does not support more precision.</p>
  <p>They are fit for one purpose: <strong>ranking foods against each other</strong> so you can
     decide what to substitute. They are not fit for use as absolute probabilities, and they
     should never be attributed to CDC, FDA or any state health department.</p>
</section>

<section aria-labelledby="m2">
  <h2 id="m2">The calculation, step by step</h2>

  <h3>Step 1 &mdash; Estimate true illnesses, not just reported ones</h3>
  <p>Reported cases undercount real infections badly. Cyclosporiasis is frequently
     misdiagnosed as ordinary traveler's diarrhea, and many people never get a stool test.
     CDC's foodborne burden model has historically applied an underdiagnosis multiplier of
     about <strong>83&times;</strong> for <em>Cyclospora cayetanensis</em>, with an
     underreporting multiplier of 1.0.{cite(['cdc-surveillance-1115', 'pmc-challenges', 'thehill-underreported'], smap)}</p>
  <p>We treat that 83&times; figure as an upper bound rather than a central estimate, because it
     was derived when detection depended on specifically requested stool ova-and-parasite
     testing. Multiplex PCR gastrointestinal panels are now widely used and detect
     <em>Cyclospora</em> without a specific request, which mechanically raises ascertainment.
     Against that, the {ns['probable_under_investigation']:,} probable cases already under
     investigation show real detection is running well ahead of confirmation.</p>
  <p>So from {ns['lab_confirmed']:,} lab-confirmed cases since May 1, we carry a range of
     roughly <strong>100,000 to 900,000 true illnesses</strong> nationally over the season,
     with a working central value near 250,000. The wide range is honest, not decorative:
     it is the single largest source of uncertainty in every number on this site.</p>

  <h3>Step 2 &mdash; Estimate servings eaten</h3>
  <p>USDA Economic Research Service per-capita availability data gives the denominator.
     Iceberg lettuce availability was about <strong>12.4 lb per person per year</strong>
     (a record low, down from 24 lb in the 1990s); romaine and leaf lettuce together run
     about <strong>18 lb per person per year</strong>.{cite(['usda-lettuce'], smap)}</p>
  <p>For iceberg, across roughly 342 million people that is about 4.2 billion lb per year, or
     about 1.1 billion lb over the ~14-week outbreak window. At a serving of about 3 oz
     (0.19 lb) &mdash; a taco's worth of shredded lettuce or a side salad &mdash; that is on
     the order of <strong>6 billion servings of iceberg lettuce nationally</strong> during
     the window.</p>

  <h3>Step 3 &mdash; Divide, then adjust for how much of the supply was implicated</h3>
  <p>Dividing illnesses by servings gives an average. But the recalled product was one
     supplier's central-Mexico-sourced lettuce, which is a small fraction of total U.S. iceberg
     supply &mdash; most U.S. summer iceberg is domestic, from California's Salinas Valley.
     Concentrating the outbreak-attributable illnesses into that small implicated fraction is
     what produces the roughly 1-in-200-to-1-in-2,000 figure for recalled product, while
     leaving non-recalled iceberg two to three orders of magnitude lower.</p>

  <h3>Step 4 &mdash; Sanity-check against a population anchor</h3>
  <p>A cross-check we can state plainly: 100,000 to 900,000 illnesses across ~342 million
     people over ~14 weeks is a seasonal per-person risk of roughly 1 in 400 to 1 in 3,400.
     A typical person eats on the order of 100&ndash;200 servings of raw produce in that
     window. That implies an <strong>average risk of about 1 in 40,000 to 1 in 700,000 per
     raw produce serving</strong>, across all produce.</p>
  <p>Every per-food number should sit sensibly around that anchor &mdash; implicated foods
     above it, cooked and peeled foods well below it. They do. That consistency check is the
     main reason to trust the <em>ordering</em> of the estimates even though the absolute
     values are soft.</p>
</section>

<section aria-labelledby="m3">
  <h2 id="m3">How mitigation effects were estimated</h2>
  <ul class="method-list">
    <li><strong>Cooking (to ~158 F / 70 C):</strong> treated as near-complete elimination,
        two to three orders of magnitude. This is the best-supported control.</li>
    <li><strong>Peeling:</strong> roughly one to two orders of magnitude, since contamination
        is a surface phenomenon. Discounted slightly for knife cross-contamination from rind
        to flesh.</li>
    <li><strong>Avoiding recalled product:</strong> the dominant effect for iceberg, worth
        several orders of magnitude, because it removes the implicated supply entirely rather
        than reducing dose.</li>
    <li><strong>Washing and rinsing:</strong> deliberately credited with very little &mdash;
        at most a factor of about two, and less for crinkled leaves and delicate berries.
        Cyclospora oocysts resist chlorine and adhere in surface crevices. Crediting washing
        the way one would for bacteria would badly misstate the risk here.</li>
    <li><strong>Choosing whole heads over precut or bagged:</strong> roughly a factor of two
        to five, reflecting less handling and fewer source fields pooled per package rather
        than any effect on contamination itself.</li>
    <li><strong>Retailer recall programs:</strong> a modest effect, acting on speed of removal
        rather than probability of contamination. Loyalty-card notification shortens the window
        during which a household keeps eating a recalled product, but cannot act before a
        recall is issued.</li>
  </ul>
</section>

<section aria-labelledby="m4">
  <h2 id="m4">Known weaknesses of this method</h2>
  <ol class="weaknesses">
    <li><strong>The underdiagnosis multiplier dominates everything.</strong> A range of
        100,000 to 900,000 true illnesses is a factor of nine, and it propagates into every
        number on the site.</li>
    <li><strong>Per-capita availability is not consumption.</strong> USDA availability data
        does not subtract household and retail waste, which is substantial for leafy greens.
        This inflates the serving denominator and therefore understates per-serving risk,
        probably by tens of percent.</li>
    <li><strong>National averages hide geography.</strong> Risk was heavily concentrated in
        the outbreak states. A national per-serving average understates risk there and
        overstates it elsewhere, potentially by an order of magnitude.</li>
    <li><strong>Attribution across four concurrent investigations is unresolved.</strong>
        Most 2026 cases are not tied to any cluster. Splitting illnesses between iceberg
        lettuce and other commodities involves judgment, and if cilantro or cucumbers are
        later confirmed, their estimates should move up and iceberg's down.</li>
    <li><strong>No positive product sample exists.</strong> The iceberg attribution rests
        entirely on epidemiology and traceback. That is legitimate and often decisive
        evidence, but it means we cannot calibrate against a measured contamination rate.</li>
    <li><strong>Risk is not static.</strong> These estimates describe the current window.
        Post-recall, iceberg risk falls; if a new commodity is named, that estimate is wrong
        until updated.</li>
  </ol>
</section>

<section aria-labelledby="mbasis">
  <h2 id="mbasis">Why the comparisons are per-occasion, not per-year</h2>
  <p>Every risk figure on this site is <strong>per serving</strong>. Familiar published
     odds are almost never quoted that way &mdash; they come per year, or across a whole
     lifetime. Putting a per-serving number beside a per-lifetime number is not a
     comparison at all, and it is the single easiest way to mislead someone with risk
     statistics.</p>
  <p>An earlier version of this page solved that by converting the food risks to a
     per-year basis. That worked arithmetically but broke down in practice: annualising
     a recalled product that had been withdrawn from sale produced an alarming figure
     for a food nobody could buy. So the conversion now runs the other way &mdash; the
     anchors are converted to a single occasion, and the food figures stay in the unit
     the rest of the site uses.</p>
  <p>Two conversions do real work and are worth stating here as well as on the chart:</p>
  <ul class="method-list">
    <li><strong>Being in a car accident, per trip.</strong> NHTSA recorded about
        6.14 million police-reported crashes in 2023 across about 3,247 billion vehicle
        miles &mdash; roughly 189 crashes per 100 million miles. At the 2022 National
        Household Travel Survey's average trip of about 13 miles, one trip carries about
        189 &times; 13 / 100,000,000, or roughly <strong>1 in 41,000 per trip</strong>.
        This counts any police-reported crash, from a scraped bumper upward. It excludes
        minor collisions never reported to police, which some estimates suggest could be
        about as numerous again; if so the real figure is nearer 1 in 20,000. We show the
        police-reported figure and state the uncertainty rather than picking a midpoint
        that no source supports.</li>
    <li><strong>Food poisoning from any cause, per meal.</strong> CDC's 48 million
        illnesses a year, across about 342 million people eating roughly three meals a
        day, is about 375 billion meals and therefore roughly
        <strong>1 in 7,800 per meal</strong>. The three-meals-a-day figure is our
        assumption, not CDC's.</li>
  </ul>
  <p>An earlier version of this page used the risk of <em>dying</em> in a car crash,
     which was a poor comparator: every food figure here is a risk of <em>getting ill</em>,
     and setting an illness risk beside a fatality risk invites the reader to equate
     them. Any-crash is a much closer match in kind, and it happens to land in the middle
     of the food range rather than far off the end of it, which makes it more useful as
     well as more honest. Severity still varies within both &mdash; a scraped bumper is
     not a week of illness &mdash; and the chart says so.</p>
</section>

<section aria-labelledby="mcolor">
  <h2 id="mcolor">Why the risk scale is not red-amber-green</h2>
  <p>The obvious colour scheme for a risk page is a traffic light. We measured it and
     rejected it. Against the green used for low risk, the orange used for moderate risk
     separates by only &Delta;E 5.6 under protanopia &mdash; far below the &Delta;E 8 floor
     for distinguishable marks. A red-amber-green risk scale is close to unreadable for
     exactly the people who most need to read a risk scale.</p>
  <p>The chart therefore uses a single blue hue where <strong>lightness</strong> carries
     magnitude, which survives all common forms of colour-vision deficiency. Every mark also
     carries a text label, so colour is never the only channel.</p>
</section>

{glossary()}

<section aria-labelledby="m5">
  <h2 id="m5">Where the numbers actually come from</h2>
  <p>The case counts on this site &mdash; confirmed cases, probable cases, hospitalisations,
     deaths &mdash; originate with CDC surveillance. But they reached this page through
     <strong>news reporting of that surveillance</strong>, not from CDC directly. Both
     cdc.gov and fda.gov refuse automated requests: CDC returns 403, and FDA returns 404 on
     every URL including its own homepage. Nobody working on this site has read those
     figures off an agency page.</p>
  <p>So each figure is cited to the reporting that actually carried it. That is a weaker
     citation than an agency document, and the sourcing markers say so: the case counts
     carry a <strong>news</strong> marker rather than an agency one. The agency pages are
     still listed, under &ldquo;where to check for updates&rdquo; on the
     <a href="sources.html">sources page</a>, because that is where you should go to
     confirm anything that matters.</p>
  <p>The alternative &mdash; citing a CDC page for a number we took from a news article
     about that page &mdash; would look more authoritative and be less true. A citation
     should point at where a claim came from, not at where it originated.</p>
  <h3>What this does and does not affect</h3>
  <ul>
    <li><strong>Outbreak counts:</strong> reported by journalists, cited to them, marked as
        news-sourced. Most likely to be stale or revised.</li>
    <li><strong>Pathogen behaviour</strong> &mdash; that cooking to about 158&nbsp;F
        inactivates it, that washing does not reliably work, that peeling removes surface
        contamination &mdash; comes from agency pages that <em>are</em> reachable, including
        the Public Health Agency of Canada and Michigan's health department. Those citations
        are as strong as they look.</li>
    <li><strong>Comparison anchors</strong> come from NHTSA, the NHTS, the National Weather
        Service and the CDC Foundation, all reachable and spot-checked automatically.</li>
  </ul>
  <p>A related note for anyone running the link checker: an automated request to fda.gov
     returns 404 for every URL including the homepage. That is bot-blocking, not a missing
     page, and a checker that treats 404 as &ldquo;dead&rdquo; will wrongly report the FDA
     citations as broken.</p>
</section>

<section aria-labelledby="m6">
  <h2 id="m6">Reproducing and updating this</h2>
  <p>All content lives in <code>data/outbreak.json</code>, <code>data/foods.json</code> and
     <code>data/sources.json</code>. Editing those and running <code>python3 build.py</code>
     regenerates the site; <code>python3 tools/validate.py</code> checks it. There are no
     dependencies and no build toolchain. Every figure should be traceable to a numbered entry
     on the sources page; if you find one that is not, that is a bug worth filing.</p>
</section>
</div>
"""
    return page(
        "Methodology - U.S. Cyclospora outbreak risk assessment",
        "How the per-serving risk estimates were calculated, what they assume, "
        "and where the method is weak.",
        body, "methodology.html", outbreak["as_of"],
    )


# --------------------------------------------------------------------------
# sources
# --------------------------------------------------------------------------

def build_sources(outbreak, sources_doc, smap):
    out = []
    for tier_id, tier_name, tier_note in TIERS:
        items = [s for s in ordered_sources(sources_doc) if s["tier"] == tier_id]
        if not items:
            continue
        rows = []
        for s in items:
            rows.append(f"""    <li id="{e(s['id'])}" value="{smap[s['id']]['_n']}">
      <a href="{e(s['url'])}" rel="noopener">{e(s['title'])}</a>
      <span class="pub">{e(s['publisher'])}</span>
      <span class="url">{e(s['url'])}</span>
    </li>""")
        out.append(f"""  <h3>{tier_name}</h3>
  <p class="tier-note">{tier_note}</p>
  <ol class="sources">
{chr(10).join(rows)}
  </ol>""")

    body = f"""
<div class="wrap page-body">
<h1>Sources</h1>
<p class="page-lede">Every source used, graded by how much weight it carries.</p>

<section aria-labelledby="s1">
  <h2 id="s1">Full list</h2>
  <p class="section-intro">Numbers in the text link here. As noted in the
     <a href="methodology.html#m5">methodology</a>, the primary agency pages could not be
     fetched directly from the build environment, so several agency figures reach this site
     by way of secondary reporting that cites them.</p>
{chr(10).join(out)}
</section>

<section aria-labelledby="s2">
  <h2 id="s2">Where to check for updates</h2>
  <p>This page is a snapshot. For live information, go to the agencies directly:</p>
  <ul class="links">
    <li><a href="https://www.cdc.gov/cyclosporiasis/outbreaks/07-26/index.html" rel="noopener">CDC &mdash; current Cyclospora outbreak page</a></li>
    <li><a href="https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts" rel="noopener">FDA &mdash; recalls, market withdrawals and safety alerts</a></li>
    <li><a href="https://www.cdc.gov/cyclosporiasis/php/surveillance/index.html" rel="noopener">CDC &mdash; cyclosporiasis surveillance</a></li>
    <li>Your state health department, which will have the most locally relevant guidance.</li>
  </ul>
</section>
</div>
"""
    return page(
        "Sources - U.S. Cyclospora outbreak risk assessment",
        "Every source used, graded by authority, with links to the primary agency pages.",
        body, "sources.html", outbreak["as_of"],
    )


FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="7" fill="#1c5cab"/>
<circle cx="14.5" cy="14" r="8" fill="none" stroke="#fff" stroke-width="2.2"/>
<path d="m20.8 20.6 5 5" stroke="#fff" stroke-width="3" stroke-linecap="round"/>
<path d="M18.4 9.6c-5.4 0-8.7 2.7-8.7 6.5 0 1 .3 1.8.8 2.2.9-1.2 2.5-2.6 4.7-3.3
-1.6 1-3 2.4-3.8 4.3.6.3 1.3.5 2 .5 4 0 5.6-4.3 5-10.2Z" fill="#fff"/>
</svg>"""


def main():
    outbreak = load("outbreak.json")
    foods = load("foods.json")
    sources_doc = load("sources.json")
    comparisons = load("comparisons.json")
    history = load_history()
    smap = source_map(sources_doc)

    SITE.mkdir(exist_ok=True)
    (SITE / "assets").mkdir(exist_ok=True)
    (SITE / "assets" / "favicon.svg").write_text(FAVICON, encoding="utf-8")

    pages = {
        "index.html": build_index(outbreak, foods, comparisons, history, smap),
        "methodology.html": build_methodology(outbreak, smap),
        "sources.html": build_sources(outbreak, sources_doc, smap),
    }
    for name, content in pages.items():
        (SITE / name).write_text(content, encoding="utf-8")
        print(f"wrote site/{name} ({len(content):,} bytes)")

    bad = []
    for f in foods["foods"]:
        for sid in f.get("sources", []):
            if sid not in smap:
                bad.append((f["name"], sid))
    for c in outbreak["critical_caveats"]:
        for sid in c.get("sources", []):
            if sid not in smap:
                bad.append((c["title"], sid))
    if bad:
        raise SystemExit(f"unknown source ids referenced: {bad}")
    print(f"ok: {len(foods['foods'])} foods, {len(sources_doc['sources'])} sources, "
          f"all ids resolve")


if __name__ == "__main__":
    main()
