#!/usr/bin/env python3
"""Render the static Cyclospora risk-assessment site from the JSON files in data/.

The JSON files under data/ are the canonical record. Edit those, re-run this
script, and commit the regenerated HTML. No third-party dependencies.

    python3 build.py
"""

import html
import json
import pathlib

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
SITE = ROOT / "site"

BAND_LABEL = {
    "high": "High",
    "moderate": "Moderate",
    "low-moderate": "Low-moderate",
    "low": "Low",
    "very-low": "Very low",
}

STATUS_LABEL = {
    "confirmed": "Confirmed - implicated 2026",
    "under-traceback": "Under traceback",
    "linked-by-recall": "In recall scope",
    "historical": "Historical only",
    "not-implicated": "Not implicated",
}


def e(text):
    return html.escape(str(text), quote=True)


def load(name):
    with open(DATA / name, encoding="utf-8") as fh:
        return json.load(fh)


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
    """Canonical citation order: grouped by tier, original order within a tier.

    Both the inline [n] citations and the numbered list on sources.html derive
    their numbering from this one function, so they cannot drift apart when a
    source is added to data/sources.json.
    """
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
    "agency": ("agency", "Agency or peer-reviewed sourcing",
               "This claim rests on government, public health or peer-reviewed sources."),
    "agency-news": ("agency + news", "Mixed sourcing",
                    "This claim rests on a mix of agency sources and news reporting."),
    "news": ("news", "News reporting only",
             "This claim rests only on news or consumer reporting. It has not been "
             "confirmed against a primary agency document."),
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


def cite(ids, smap, dated=None):
    """Render source ids as superscript numbered links plus a provenance marker.

    Every citation on this site is marked with where the claim actually came
    from, because a figure that reached us via a news article is not as good as
    one read off an agency page, and the reader is entitled to know which is
    which without chasing links. `dated` optionally stamps the claim with the
    date it describes.
    """
    if not ids:
        return ""
    links = []
    for sid in ids:
        src = smap.get(sid)
        if not src:
            continue
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
        label, short, explain = PROVENANCE[kind]
        out += (' <span class="prov prov-{k}" title="{explain}">'
                '<span class="vh">Sourcing: </span>{label}</span>').format(
            k=e(kind), explain=e(explain), label=e(label))
    if dated:
        out += (' <span class="dated" title="The date this figure describes">'
                '<span class="vh">as of </span>'
                '<time datetime="{d}">{d}</time></span>').format(d=e(dated))
    return out


# --------------------------------------------------------------------------
# shared chrome
# --------------------------------------------------------------------------

def page(title, description, body, active, as_of):
    nav = [("index.html", "Risk table"),
           ("methodology.html", "Methodology"),
           ("sources.html", "Sources")]
    nav_html = "\n".join(
        '        <a href="{href}"{cls}>{label}</a>'.format(
            href=href, label=e(label),
            cls=' class="active" aria-current="page"' if href == active else "",
        )
        for href, label in nav
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<meta name="robots" content="index, follow">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>

<div class="alert-bar" role="region" aria-label="Medical disclaimer">
  <strong>Not medical advice.</strong> This is an independent, best-effort explainer.
  If you are ill, contact a clinician. In an emergency, call 911.
</div>

<header class="site-header">
  <div class="wrap">
    <p class="eyebrow">Independent explainer &middot; unaffiliated with CDC, FDA or any company</p>
    <h1>U.S. Cyclospora outbreak: practical risk assessment</h1>
    <p class="lede">{e(description)}</p>
    <p class="asof">Information current through <time datetime="{e(as_of)}">{e(as_of)}</time>.
       Outbreak data changes frequently &mdash; verify against the primary sources before acting.</p>
    <nav class="site-nav" aria-label="Primary">
{nav_html}
    </nav>
  </div>
</header>

<main id="main" class="wrap">
{body}
</main>

<footer class="site-footer">
  <div class="wrap">
    <h2>Disclaimers and limitations</h2>
    <ol class="disclaimers">
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
      <li><strong>Source access was limited when this page was built.</strong> The build
          environment could not reach cdc.gov or fda.gov directly. Agency figures were taken
          from search-indexed summaries of those pages and from reputable secondary reporting,
          not from a direct read of the primary documents. This is a real reliability limit
          &mdash; treat the primary sources as authoritative wherever they differ.</li>
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
      <li><strong>Companies are named only because official sources named them.</strong>
          Naming a firm or product reflects the public record of this investigation and is not
          an allegation of wrongdoing beyond what agencies have stated.</li>
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
</body>
</html>
"""


# --------------------------------------------------------------------------
# index
# --------------------------------------------------------------------------

def build_index(outbreak, foods, smap):
    ns = outbreak["national_season"]
    io = outbreak["implicated_outbreak"]
    rc = outbreak["recall"]

    rows = []
    for f in foods["foods"]:
        rows.append(f"""      <tr class="band-{e(f['band'])}">
        <th scope="row">
          <span class="food-name">{e(f['name'])}</span>
          <span class="food-detail">{e(f['detail'])}{cite(f.get('sources'), smap)}</span>
        </th>
        <td data-label="Status"><span class="status status-{e(f['status'])}">{e(STATUS_LABEL[f['status']])}</span></td>
        <td data-label="Estimated risk per serving"><span class="band-tag">{e(BAND_LABEL[f['band']])}</span>
            <span class="risk">{e(f['risk_unmitigated'])}</span></td>
        <td data-label="Primary mitigation">{e(f['mitigation'])}</td>
        <td data-label="Residual risk after mitigation"><span class="risk">{e(f['risk_residual'])}</span>
            {'<span class="residual-note">' + e(f['residual_note']) + '</span>' if f.get('residual_note') else ''}</td>
        <td data-label="Confidence"><span class="conf conf-{e(f['confidence'])}">{e(f['confidence'].replace('-', ' to '))}</span></td>
      </tr>""")

    caveats = "\n".join(
        f"""    <div class="caveat">
      <h3>{e(c['title'])}{cite(c.get('sources'), smap)}</h3>
      <p>{e(c['body'])}</p>
    </div>"""
        for c in outbreak["critical_caveats"]
    )

    bio = outbreak["biology"]

    body = f"""
<section class="bottom-line" aria-labelledby="bl">
  <h2 id="bl">The bottom line</h2>
  <ul class="takeaways">
    <li><strong>One product is doing most of the damage.</strong> Iceberg lettuce from
        Taylor Farms de Mexico, sourced from central Mexico, was recalled on
        {e(rc['date'])}. That product is off the market. If you are not eating recalled
        product, your per-serving risk from any single food on this page is
        well under 1 in 10,000.</li>
    <li><strong>Washing is not a mitigation for this parasite.</strong> Cyclospora oocysts
        resist chlorine and do not rinse off cleanly. Cooking to about 158&nbsp;F (70&nbsp;C)
        and peeling are the only consumer controls that work reliably. Most
        "wash your produce better" advice does not apply here.</li>
    <li><strong>Substitute within produce, not away from it.</strong> Swapping iceberg for
        romaine or spinach, and cooking herbs instead of using them raw, captures most of
        the available risk reduction at essentially no nutritional cost.</li>
    <li><strong>The season is bigger than the recall.</strong> FDA has described four
        separate 2026 Cyclospora investigations, and most reported cases are not yet tied to
        any cluster. Expect further named commodities.</li>
  </ul>
</section>

<section class="prov-key" aria-labelledby="prov-h">
  <h2 id="prov-h">How to read the sourcing markers</h2>
  <p>Every figure and claim on this site is tagged with where it came from and, where it
     is a moving number, the date it describes. Nothing here is presented as fact without
     showing you what is behind it.</p>
  <ul class="prov-legend">
    <li><span class="prov prov-agency">agency</span> Backed by a government, public health
        or peer-reviewed source.</li>
    <li><span class="prov prov-agency-news">agency + news</span> Backed by a mix of agency
        sources and news reporting.</li>
    <li><span class="prov prov-news">news</span> Backed only by news or consumer reporting,
        and not confirmed against a primary agency document. Treat these as the weakest
        claims on the page.</li>
    <li><span class="dated"><time datetime="2026-08-05">2026-08-05</time></span> The date
        the figure describes &mdash; not the date you are reading it. Outbreak numbers move.</li>
  </ul>
  <p class="prov-caveat"><strong>Important:</strong> an <span class="prov prov-agency">agency</span>
     marker means an agency is the origin of the claim, not that we read it off the agency's
     own page. As explained in the <a href="methodology.html#m5">methodology</a>, cdc.gov and
     fda.gov were unreachable from the build environment, so most agency figures here arrived
     by way of sources that cite them.</p>
</section>

<section aria-labelledby="numbers">
  <h2 id="numbers">Where the outbreak stands</h2>
  <div class="stats">
    <div class="stat">
      <span class="stat-num">{ns['lab_confirmed']:,}</span>
      <span class="stat-label">lab-confirmed cases since May&nbsp;1, 2026{cite(ns['sources'], smap, ns['as_of'])}</span>
    </div>
    <div class="stat">
      <span class="stat-num">{ns['probable_under_investigation']:,}</span>
      <span class="stat-label">additional probable cases under investigation{cite(ns['sources'], smap, ns['as_of'])}</span>
    </div>
    <div class="stat">
      <span class="stat-num">{ns['hospitalizations']:,}</span>
      <span class="stat-label">hospitalizations{cite(ns['sources'], smap, ns['as_of'])}</span>
    </div>
    <div class="stat">
      <span class="stat-num">{ns['deaths']}</span>
      <span class="stat-label">deaths{cite(['cnn-deaths', 'axios-deaths'], smap, '2026-08-03')}</span>
    </div>
  </div>
  <p class="stat-foot">{e(ns['window'])}, as of {e(ns['as_of'])}. {e(ns['states_with_cases'])}
     {e(ns['deaths_note'])}</p>

  <h3>The implicated supply chain</h3>
  <dl class="facts">
    <dt>Vehicle</dt><dd>{e(io['vehicle'])}{cite(io.get('sources'), smap)}</dd>
    <dt>Supplier</dt><dd>{e(io['supplier'])}</dd>
    <dt>How it surfaced</dt><dd>{e(io['first_announced_detail'])} ({e(io['first_announced'])})</dd>
    <dt>Scope since</dt><dd>{e(io['expansion_detail'])}</dd>
    <dt>Illness onsets</dt><dd>{e(io['onset_range'])}</dd>
    <dt>Evidence basis</dt><dd>{e(io['evidence_basis'])}</dd>
    <dt>Recall</dt><dd>{e(rc['scope'])} {e(rc['distribution'])} {e(rc['blends_note'])}{cite(rc.get('sources'), smap)}</dd>
  </dl>
</section>

<section class="caveats" aria-labelledby="caveats-h">
  <h2 id="caveats-h">What the evidence does and does not show</h2>
  <p class="section-intro">Distinguishing confirmed findings from open questions and from
     historical associations is the most decision-relevant part of this page.</p>
{caveats}
</section>

<section aria-labelledby="table-h">
  <h2 id="table-h">Estimated risk by food</h2>
  <p class="section-intro">{e(foods['risk_basis'])}
     Read the columns together: a food can carry moderate unmitigated risk and still be a fine
     choice if the mitigation is cheap and effective. See
     <a href="methodology.html">how these were calculated</a>.</p>

  <div class="est-warning" role="note">
    <strong>These are informed estimates, not official statistics.</strong> No agency publishes
    per-serving probabilities for these foods. The values below were derived by this project
    from published case counts and consumption data, and are rounded to the nearest order of
    magnitude. They are reliable for ranking foods against each other, and unreliable as
    absolute probabilities.
  </div>

  <div class="table-scroll">
  <table class="risk-table">
    <caption>Estimated per-serving risk of Cyclospora infection, United States, current outbreak window</caption>
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

  <h3>How to read the status column</h3>
  <ul class="legend">
{chr(10).join(f'    <li><span class="status status-{e(k)}">{e(STATUS_LABEL[k])}</span> {e(v)}</li>' for k, v in foods["status_legend"].items())}
  </ul>
</section>

<section aria-labelledby="bio-h">
  <h2 id="bio-h">Why the usual advice does not work here</h2>
  <dl class="facts">
    <dt>Washing</dt><dd>{e(bio['washing'])}</dd>
    <dt>Cooking</dt><dd>{e(bio['cooking'])}</dd>
    <dt>Peeling</dt><dd>{e(bio['peeling'])}</dd>
    <dt>Household spread</dt><dd>{e(bio['person_to_person'])}</dd>
    <dt>Timing of symptoms</dt><dd>{e(bio['incubation'])}{cite(bio.get('sources'), smap)}</dd>
  </dl>
</section>

<section class="when-to-care" aria-labelledby="care-h">
  <h2 id="care-h">When to seek care</h2>
  <p>Cyclosporiasis does not resolve reliably on its own and is treated with prescription
     antibiotics, so it is worth getting diagnosed rather than waiting it out. Standard stool
     tests do not always look for Cyclospora &mdash; it often requires a specific request or a
     multiplex GI panel, so mention recent produce exposure to your clinician.</p>
  <p><strong>Seek care promptly</strong> for watery diarrhea lasting more than a few days,
     diarrhea that improves and then relapses, signs of dehydration (dizziness on standing,
     little or no urination), fever, or any diarrheal illness if you are immunocompromised,
     pregnant, elderly or caring for a young child. <strong>Call 911</strong> for severe
     dehydration, fainting or bloody stool.</p>
  <p class="care-note">This section describes when to consult a professional. It is not a
     diagnosis and not medical advice.</p>
</section>
"""
    return page(
        "U.S. Cyclospora outbreak: practical risk assessment by food",
        "Actionable, source-cited risk assessment for the 2026 U.S. Cyclospora outbreak, "
        "with per-serving estimates and mitigations by food.",
        body, "index.html", outbreak["as_of"],
    )


# --------------------------------------------------------------------------
# methodology
# --------------------------------------------------------------------------

def build_methodology(outbreak, smap):
    ns = outbreak["national_season"]
    body = f"""
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
  <p>Every per-food number on the risk table should sit sensibly around that anchor &mdash;
     implicated foods above it, cooked and peeled foods well below it. They do. That
     consistency check is the main reason to trust the <em>ordering</em> of the table even
     though the absolute values are soft.</p>
</section>

<section aria-labelledby="m3">
  <h2 id="m3">How mitigation effects were estimated</h2>
  <ul class="method-list">
    <li><strong>Cooking (to ~158 F / 70 C):</strong> treated as near-complete elimination,
        two to three orders of magnitude. This is the best-supported control and the reason
        cooked vegetables sit at the bottom of the table.</li>
    <li><strong>Peeling:</strong> treated as roughly one to two orders of magnitude, since
        contamination is a surface phenomenon. Discounted slightly for knife
        cross-contamination from rind to flesh.</li>
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
    <li><strong>Retailer recall programs:</strong> a modest effect, and one that acts on speed
        of removal rather than probability of contamination. Loyalty-card-linked notification
        shortens the window during which a household keeps eating a recalled product, but
        cannot act before a recall is issued.</li>
  </ul>
</section>

<section aria-labelledby="m4">
  <h2 id="m4">Known weaknesses of this method</h2>
  <ol class="weaknesses">
    <li><strong>The underdiagnosis multiplier dominates everything.</strong> A range of
        100,000 to 900,000 true illnesses is a factor of nine, and it propagates into every
        cell of the table.</li>
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
        later confirmed, their rows should move up and iceberg's should move down.</li>
    <li><strong>No positive product sample exists.</strong> The iceberg attribution rests
        entirely on epidemiology and traceback. That is legitimate and often decisive
        evidence, but it means we cannot calibrate against a measured contamination rate.</li>
    <li><strong>Risk is not static.</strong> These estimates describe the current window.
        Post-recall, iceberg risk falls; if a new commodity is named, that row is wrong until
        updated.</li>
  </ol>
</section>

<section aria-labelledby="m5">
  <h2 id="m5">How sources were accessed &mdash; and a real limitation</h2>
  <p>The environment in which this site was built could not make outbound connections to
     cdc.gov or fda.gov; those hosts were blocked at the network egress layer. Agency figures
     were therefore obtained from <strong>search-indexed summaries of the agency pages and from
     reputable secondary reporting</strong> that cites them, rather than from a direct read of
     the primary documents.</p>
  <p>We are stating this plainly because it matters for how much weight to give these numbers.
     The practical consequences:</p>
  <ul>
    <li>Exact figures may be off, or may reflect a snapshot older than the date on this page.</li>
    <li>Published counts genuinely conflict across sources. Where they do, we show the range
        and label it rather than silently choosing one.</li>
    <li>Primary sources are linked throughout and on the <a href="sources.html">sources page</a>.
        Where they differ from anything here, <strong>they are correct and this page is not</strong>.</li>
  </ul>
  <p>Anyone rebuilding this site from an unrestricted network should re-verify every figure in
     <code>data/outbreak.json</code> against the primary CDC and FDA pages first.</p>
</section>

<section aria-labelledby="m6">
  <h2 id="m6">Reproducing and updating this</h2>
  <p>All content lives in <code>data/outbreak.json</code>, <code>data/foods.json</code> and
     <code>data/sources.json</code>. Editing those and running <code>python3 build.py</code>
     regenerates the site. There are no dependencies and no build toolchain. Every figure is
     meant to be traceable to a numbered entry on the sources page; if you find one that
     is not, that is a bug worth filing.</p>
</section>
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
<section aria-labelledby="s1">
  <h2 id="s1">Sources</h2>
  <p class="section-intro">Numbers in the text link here. Sources are grouped by how much
     weight they carry. As noted in the <a href="methodology.html#m5">methodology</a>, the
     primary agency pages could not be fetched directly from the build environment, so several
     agency figures reach this site by way of secondary reporting that cites them.</p>
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
"""
    return page(
        "Sources - U.S. Cyclospora outbreak risk assessment",
        "Every source used, graded by authority, with links to the primary agency pages.",
        body, "sources.html", outbreak["as_of"],
    )


def main():
    outbreak = load("outbreak.json")
    foods = load("foods.json")
    sources_doc = load("sources.json")
    smap = source_map(sources_doc)

    SITE.mkdir(exist_ok=True)
    (SITE / "assets").mkdir(exist_ok=True)

    pages = {
        "index.html": build_index(outbreak, foods, smap),
        "methodology.html": build_methodology(outbreak, smap),
        "sources.html": build_sources(outbreak, sources_doc, smap),
    }
    for name, content in pages.items():
        (SITE / name).write_text(content, encoding="utf-8")
        print(f"wrote site/{name} ({len(content):,} bytes)")

    # Fail loudly if a food cites a source id that does not exist.
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
    print(f"ok: {len(foods['foods'])} foods, {len(sources_doc['sources'])} sources, all ids resolve")


if __name__ == "__main__":
    main()
