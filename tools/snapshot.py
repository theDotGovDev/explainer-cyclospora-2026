#!/usr/bin/env python3
"""Append the current outbreak figures to data/history.jsonl.

    python3 tools/snapshot.py

The site only ever shows the latest numbers, which means every earlier figure is
overwritten and lost - and this outbreak's counts have already been revised more
than once. This keeps an append-only record so the revisions are visible instead
of silently replaced.

JSON Lines: one self-describing record per line, appended, never rewritten.
Diffs stay readable, and a corrupted line cannot take the rest of the file with
it. No dependency needed to read or write it.

Idempotent: re-running with unchanged figures does nothing.
"""

import collections
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.jsonl"
SERIES = {"national_season", "iceberg_cluster"}


def read_history():
    if not HISTORY.exists():
        return []
    out = []
    for n, line in enumerate(HISTORY.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as ex:
            raise SystemExit(f"history.jsonl line {n} is not valid JSON: {ex}")
    return out


def main():
    outbreak = json.loads((ROOT / "data" / "outbreak.json").read_text(encoding="utf-8"))
    ns = outbreak["national_season"]
    record = collections.OrderedDict([
        ("observed", ns["as_of"]),
        ("recorded", datetime.date.today().isoformat()),
        ("series", "national_season"),
        ("metrics", collections.OrderedDict([
            ("lab_confirmed", ns["lab_confirmed"]),
            ("probable", ns["probable_under_investigation"]),
            ("hospitalizations", ns["hospitalizations"]),
            ("deaths", ns["deaths"]),
        ])),
        ("sources", ns["sources"]),
    ])

    history = read_history()
    prior = [r for r in history if r["series"] == "national_season"]
    if prior:
        latest = max(prior, key=lambda r: r["observed"])
        same = (latest["observed"] == record["observed"]
                and latest["metrics"].get("lab_confirmed") == record["metrics"]["lab_confirmed"]
                and latest["metrics"].get("probable") == record["metrics"]["probable"]
                and latest["metrics"].get("hospitalizations") == record["metrics"]["hospitalizations"]
                and latest["metrics"].get("deaths") == record["metrics"]["deaths"])
        if same:
            print("no change since the last snapshot; nothing appended")
            return 0
        # Same observation date with different figures is a REVISION, which is
        # exactly what this log exists to capture. Keep both, distinguished by
        # the date we recorded them.
        if latest["observed"] == record["observed"]:
            if any(r["recorded"] == record["recorded"] for r in prior
                   if r["observed"] == record["observed"]):
                print(f"a revision for {record['observed']} was already recorded "
                      f"today; edit that line rather than appending another",
                      file=sys.stderr)
                return 1
            print(f"figures for {record['observed']} changed - recording a revision")
        if record["observed"] < latest["observed"]:
            print(f"refusing to append: observed {record['observed']} is older than "
                  f"the latest logged observation {latest['observed']}", file=sys.stderr)
            return 1

    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"appended snapshot for {record['observed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
