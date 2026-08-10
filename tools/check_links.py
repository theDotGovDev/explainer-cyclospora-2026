#!/usr/bin/env python3
"""Fetch every cited source: check it resolves, and spot-check what it says.

Two jobs. First, confirm each URL in data/sources.json still resolves. Second,
for sources listed in data/claims.json, fetch the page and look for the figures
this site attributes to it - so a source being edited, or a number drifting, or
a citation that never supported its claim, shows up rather than sitting there
looking authoritative.

Two limits worth stating plainly, both of which the report repeats:

  * This checks that a figure APPEARS in a source. It cannot check that we
    represented the source fairly - a number can be on the page and still be
    quoted out of context. Only a human reading the source settles that.

  * cdc.gov and fda.gov refuse automated requests, CDC with 403 and FDA with
    404 on every URL including its own homepage. They cannot be checked here,
    and they are the sources carrying the outbreak case counts.

Reading the cited PDFs needs pypdf (`pip install -r requirements.txt`). Without
it those claims are SKIPped rather than guessed at.

Advisory only - run by CI with continue-on-error. A dead link or an unverifiable
figure is worth surfacing, but should never block shipping a correction to
health information.

    python3 tools/check_links.py
"""

import email
import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pdf_text  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
TIMEOUT = 25

# How much of a response body to read. HTML only needs enough to find a figure
# in the prose. A PDF needs the WHOLE FILE: its cross-reference table and EOF
# marker live at the end, so a truncated PDF is not a partial PDF, it is an
# unreadable one. Reading PDFs under the HTML-sized cap is what made the NHTSA
# crash summary look like a document nobody could parse.
HTML_BYTES = 4_000_000
PDF_BYTES = 64_000_000

# Agency and news sites routinely reject non-browser agents with 403.
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _raw(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status


def host_root(url):
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/"


def read_body(resp, cap, head=b""):
    """Read the response to end of stream, or to `cap`. Returns (bytes, hit_cap).

    Loops, because a single read(n) is only documented to return *up to* n
    bytes. Asking for four megabytes and treating whatever comes back as the
    whole file is how the NHTSA crash summary arrived with no trailer on it and
    was reported as a document with no Root object - twice, and the second time
    with our own diagnostic cheerfully calling it complete.
    """
    parts = [head]
    total = len(head)
    while total < cap:
        chunk = resp.read(min(1 << 20, cap - total))
        if not chunk:
            return b"".join(parts), False
        parts.append(chunk)
        total += len(chunk)
    return b"".join(parts), True


def unwrap_multipart(ctype, raw):
    """Pull a PDF out of a multipart response body, or return None.

    NHTSA's crashstats ViewPublication endpoint does this: it answers with a
    multipart body - WebKit form boundaries and all - carrying the PDF as a
    part, while labelling the whole response as a PDF. Handed straight to a
    parser, that is a MIME envelope wearing a PDF's content type, and the
    parser rightly says it cannot find a Root object.

    Parsed with email from the standard library rather than by hunting for
    boundaries, because a MIME body is exactly what that module is for.
    """
    if raw[:5] == b"%PDF-" or b"%PDF-" not in raw[:65536]:
        return None
    header = ctype
    if "boundary=" not in ctype.lower():
        # The response labels itself a PDF and does not declare a boundary, so
        # recover it from the body: a multipart body opens with "--<boundary>"
        # (RFC 2046). Reconstructing the header is what lets email do the rest.
        first = raw.split(b"\r\n", 1)[0].strip()
        if not first.startswith(b"--"):
            return None
        header = ('multipart/form-data; boundary="'
                  + first[2:].decode("latin-1", "replace") + '"')
    try:
        msg = email.message_from_bytes(
            b"Content-Type: " + header.encode("latin-1", "replace")
            + b"\r\n\r\n" + raw)
        if not msg.is_multipart():
            return None
        for part in msg.walk():
            payload = part.get_payload(decode=True)
            if payload and payload[:5] == b"%PDF-":
                return payload
    except Exception:  # noqa: BLE001 - a malformed envelope is a finding, not a crash
        return None
    return None


def describe(resp, raw, hit_cap):
    """Say what actually arrived, when a document would not parse.

    Every round of this investigation was lost to a diagnosis inferred from too
    little: mojibake blamed on font subsetting, a parse failure blamed on
    truncation, a short read assumed rather than measured. All three were
    wrong, and the answer - a MIME envelope wearing a PDF's content type - was
    sitting in the first twelve bytes of the body the whole time.

    So this prints what arrived rather than what it ought to have been: bytes
    promised against bytes received, the declared type and encoding, and how
    the body actually opens. Keep it even now that the case is solved; the next
    unreadable document will be unreadable for some other reason.
    """
    declared = resp.headers.get("Content-Length")
    encoding = resp.headers.get("Content-Encoding") or "none"
    bits = [f"{len(raw):,} bytes received"]
    if declared and declared.isdigit():
        want = int(declared)
        bits.append(f"Content-Length said {want:,}"
                    + ("" if want == len(raw) else " - SHORT, we lost some"))
    else:
        bits.append("no Content-Length declared")
    bits.append(f"Content-Type {resp.headers.get('Content-Type') or 'absent'}")
    bits.append(f"Content-Encoding {encoding}")
    bits.append("starts %PDF-" if raw[:5] == b"%PDF-"
                else f"does NOT start %PDF- (starts {raw[:12]!r})")
    if hit_cap:
        bits.append("HIT OUR READ CAP, so this truncation is ours")
    return ", ".join(bits)


def fetch(url, attempt=0):
    """Return (text, note). Empty text means the body could not be read."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            # Peek at the magic bytes before choosing a cap, because a server
            # that mislabels its Content-Type should not decide how much of its
            # own PDF we are willing to read.
            head = resp.read(5)
            is_pdf = "pdf" in ctype or head == b"%PDF-"
            cap = PDF_BYTES if is_pdf else HTML_BYTES
            raw, hit_cap = read_body(resp, cap, head)
            if is_pdf:
                inner = unwrap_multipart(ctype, raw)
                wrapped = ""
                if inner:
                    raw, wrapped = inner, ", unwrapped from a multipart body"
                # Returning no text puts this on the SKIP path, which is the
                # honest place for it: "we did not read this" is not the same
                # finding as "this source does not say that", and only the
                # second is evidence about a source.
                got = pdf_text.extract(raw)
                if not got.text.strip():
                    return "", f"pdf not read - {got.how} [{describe(resp, raw, hit_cap)}]"
                if not got.readable:
                    return "", ("pdf parsed but yielded no words - probably a "
                                "scan with no text layer, nothing to search")
                return got.text, f"pdf via pypdf{wrapped}"
            return raw.decode("utf-8", "replace"), ""
    except TimeoutError:
        if attempt < 1:
            return fetch(url, attempt + 1)
        return "", "timed out"
    except Exception as ex:  # noqa: BLE001 - advisory, never crash CI
        return "", f"{type(ex).__name__}: {str(ex)[:60]}"


TAGS = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)
WS = re.compile(r"\s+")


def page_text(html_text):
    """Crude tag strip. Good enough to find a figure; not a parser."""
    txt = TAGS.sub(" ", html_text)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&#39;", "'"),
                 ("&quot;", '"'), ("&mdash;", "-"), ("&ndash;", "-")):
        txt = txt.replace(a, b)
    return WS.sub(" ", txt)


def verify_claims(smap):
    """Look for each attributed figure in the source's own text."""
    path = ROOT / "data" / "claims.json"
    if not path.exists():
        return 0, 0
    doc = json.loads(path.read_text(encoding="utf-8"))
    print("\n=== verifying attributed figures ===")
    print(doc["coverage_limit"] + "\n")

    checked = unverified = skipped = 0
    for c in doc["claims"]:
        src = smap.get(c["source"])
        if not src:
            print(f"CLAIM-ERR  {c['source']:<22} not a known source id")
            unverified += 1
            continue
        text, note = fetch(src["url"])
        if not text:
            skipped += 1
            print(f"SKIP       {c['source']:<22} {note}")
            continue
        body = page_text(text) if not note.startswith("pdf") else text
        # A client-rendered page returns a shell with almost no prose. Reporting
        # that as "figure not found" is a false alarm that trains people to
        # ignore the check, so say what actually happened instead.
        if len(body.strip()) < 800:
            skipped += 1
            print(f"SKIP       {c['source']:<22} only {len(body.strip())} chars of text - "
                  f"page looks client-rendered, nothing to search")
            continue
        missing = [x for x in c["expect"] if x.lower() not in body.lower()]
        how = f"  [{note}]" if note else ""
        checked += 1
        if missing:
            unverified += 1
            print(f"NOT FOUND  {c['source']:<22} expected {missing} in the page text{how}")
            print(f"           supports: {c['supports']}")
        else:
            print(f"ok         {c['source']:<22} all {len(c['expect'])} figure(s) present{how}")

    print(f"\n{checked} source(s) text-checked, {unverified} with figures not "
          f"found, {skipped} skipped because the page could not be read.")
    print("Reminder: this only shows a figure APPEARS in the source. It cannot "
          "show the source was represented fairly.")
    return checked, unverified


def probe(url, attempt=0):
    """Return (ok, note). GET, not HEAD: many sites 405 on HEAD."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return True, f"{resp.status}"
    except urllib.error.HTTPError as ex:
        # 403/429 usually means bot-blocked or rate-limited, not a dead link.
        if ex.code in (403, 429):
            return True, f"{ex.code} (blocked to automation, not treated as dead)"
        if ex.code == 404:
            # Distinguish "this path is gone" from "this host 404s all robots".
            # Without this, a site that cloaks bot-blocking as 404 looks
            # identical to a citation URL that was simply never real - and for
            # this project that difference decides whether a source is honest.
            try:
                root = _raw(host_root(url))
                return False, (f"HTTP 404 - PATH MISSING "
                               f"(host root returned {root}, so the host is up)")
            except urllib.error.HTTPError as rex:
                # A live site's homepage does not 404. If the root gives 404 or
                # 403, the host is refusing this client wholesale rather than
                # telling us anything about the path, so we cannot conclude the
                # citation is dead. fda.gov does exactly this: it 404s every
                # request from automation, homepage included.
                return True, (f"HTTP 404 but host root also returns {rex.code} - "
                              f"INCONCLUSIVE, host blocks automation wholesale")
            except Exception:  # noqa: BLE001
                return True, "HTTP 404, host root unreachable - INCONCLUSIVE"
        return False, f"HTTP {ex.code}"
    except urllib.error.URLError as ex:
        reason = str(ex.reason)
        # A proxy refusing the CONNECT tunnel says nothing about the URL. Treat
        # it as inconclusive rather than reporting a live source as dead.
        if "Tunnel connection failed" in reason or "proxy" in reason.lower():
            return True, f"inconclusive (blocked by egress proxy: {reason})"
        return False, f"unreachable: {reason}"
    except TimeoutError:
        if attempt < 2:
            return probe(url, attempt + 1)
        return False, f"timed out after {attempt + 1} attempts"
    except Exception as ex:  # noqa: BLE001 - advisory check, never crash CI
        msg = str(ex)
        if "timed out" in msg and attempt < 2:
            return probe(url, attempt + 1)
        return False, f"error: {ex}"


def main():
    doc = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
    dead = []
    for s in doc["sources"]:
        ok, note = probe(s["url"])
        print(f"{'ok  ' if ok else 'DEAD'}  {s['id']:<26} {note:<44} {s['url']}")
        if not ok:
            dead.append((s["id"], note, s["url"]))

    print()
    smap = {s["id"]: s for s in doc["sources"]}
    _, unverified = verify_claims(smap)

    try:
        import data_sources
        data_sources.main()
    except Exception as ex:  # noqa: BLE001 - a probe must not break the checker
        print(f"\ndata source probe failed: {type(ex).__name__}: {ex}")

    if dead:
        print(f"\n{len(dead)} source link(s) did not resolve:", file=sys.stderr)
        for sid, note, url in dead:
            print(f"  {sid}: {note} - {url}", file=sys.stderr)
        return 1
    if unverified:
        print(f"\n{unverified} attributed figure(s) could not be found in their "
              f"source. Check them by hand.", file=sys.stderr)
        return 1
    print(f"all {len(doc['sources'])} source links resolved, attributed figures found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
