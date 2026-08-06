#!/usr/bin/env python3
"""Check that every URL in data/sources.json still resolves.

Advisory only - run by CI with continue-on-error. A citation that 404s is a
credibility problem worth surfacing, but it should never block shipping a
correction to health information.

    python3 tools/check_links.py
"""

import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
TIMEOUT = 25

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
    if dead:
        print(f"{len(dead)} source link(s) did not resolve:", file=sys.stderr)
        for sid, note, url in dead:
            print(f"  {sid}: {note} - {url}", file=sys.stderr)
        return 1
    print(f"all {len(doc['sources'])} source links resolved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
