#!/usr/bin/env python3
"""Probe machine-readable public sources for outbreak and recall figures.

    python3 tools/data_sources.py

Everything on this site is currently transcribed by hand from pages that block
automation. www.cdc.gov returns 403 to a script and www.fda.gov returns 404 on
every URL including its own homepage, so neither can be read or re-checked
automatically. That is the single biggest reliability problem the project has.

Both agencies publish the same underlying data on *different* hosts that are
built to be queried, and those hosts are not obviously subject to the same
blocking:

  api.fda.gov    openFDA. The food enforcement endpoint serves the FDA Recall
                 Enterprise System - the authoritative recall records, updated
                 weekly. This is where the Taylor Farms recall should appear as
                 structured data rather than as prose we retyped.

  data.cdc.gov   CDC's open data portal, running Socrata. Cyclosporiasis is a
                 nationally notifiable disease, so NNDSS weekly tables should
                 carry case counts by state and week.

This script only reports what it finds. It deliberately does not write anything
into data/ - a number arriving automatically still needs a human to decide it
belongs on a health page.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 30
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", "replace")), None
    except urllib.error.HTTPError as ex:
        body = ""
        try:
            body = ex.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001
            pass
        return None, f"HTTP {ex.code} {body}"
    except Exception as ex:  # noqa: BLE001 - probe must never crash CI
        return None, f"{type(ex).__name__}: {str(ex)[:80]}"


def section(title):
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def probe_openfda():
    section("openFDA food enforcement (api.fda.gov) - official recall records")
    queries = [
        ('recalls naming Taylor Farms',
         'https://api.fda.gov/food/enforcement.json?search='
         + urllib.parse.quote('recalling_firm:"Taylor Farms"') + '&limit=5'),
        ('recalls mentioning Cyclospora',
         'https://api.fda.gov/food/enforcement.json?search='
         + urllib.parse.quote('reason_for_recall:"Cyclospora"') + '&limit=5'),
    ]
    reachable = False
    for label, url in queries:
        data, err = get_json(url)
        if err:
            print(f"  [{label}] FAILED: {err}")
            continue
        reachable = True
        total = data.get("meta", {}).get("results", {}).get("total", 0)
        print(f"  [{label}] {total} matching record(s)")
        for r in data.get("results", [])[:3]:
            print(f"    - {r.get('recall_initiation_date', '?')} "
                  f"{r.get('recalling_firm', '?')} | {r.get('status', '?')} "
                  f"| classification {r.get('classification', '?')}")
            print(f"      states: {str(r.get('distribution_pattern', ''))[:110]}")
            print(f"      reason: {str(r.get('reason_for_recall', ''))[:110]}")
    return reachable


def probe_socrata():
    section("data.cdc.gov (Socrata) - is cyclosporiasis surveillance published?")
    cat = ("https://api.us.socrata.com/api/catalog/v1?domains=data.cdc.gov"
           "&q=cyclosporiasis&limit=10")
    data, err = get_json(cat)
    if err:
        print(f"  catalog search FAILED: {err}")
        return False
    results = data.get("results", [])
    print(f"  {data.get('resultSetSize', len(results))} dataset(s) matched "
          f"'cyclosporiasis'")
    for r in results[:10]:
        res = r.get("resource", {})
        print(f"    - {res.get('id', '?')}  {res.get('name', '?')[:70]}")
        print(f"      updated {str(res.get('updatedAt', ''))[:10]}  "
              f"https://data.cdc.gov/resource/{res.get('id', '?')}.json")
    if not results:
        print("  Nothing matched. Try a broader term - NNDSS tables are often "
              "named by table number rather than by disease.")
        data2, err2 = get_json("https://api.us.socrata.com/api/catalog/v1"
                               "?domains=data.cdc.gov&q=NNDSS%20weekly&limit=5")
        if not err2:
            for r in data2.get("results", [])[:5]:
                res = r.get("resource", {})
                print(f"    - {res.get('id', '?')}  {res.get('name', '?')[:70]}")
    return True


def main():
    print(__doc__.split("\n\n")[0])
    fda_ok = probe_openfda()
    cdc_ok = probe_socrata()

    section("what this means")
    if fda_ok:
        print("  api.fda.gov IS reachable. The recall details on this site can be")
        print("  checked against, or replaced by, the official FDA recall record")
        print("  instead of prose transcribed from a page we cannot open.")
    else:
        print("  api.fda.gov did not answer. FDA recall data stays hand-entered.")
    if cdc_ok:
        print("  data.cdc.gov IS reachable. If a cyclosporiasis dataset is listed")
        print("  above, case counts could be pulled rather than retyped.")
    else:
        print("  data.cdc.gov did not answer. CDC counts stay hand-entered.")
    print("\n  Nothing here is written into data/ automatically. A figure that")
    print("  arrives by API still needs a human to decide it belongs on a page")
    print("  that gives health guidance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
