#!/usr/bin/env python3
"""How old is the outbreak data? Prints GitHub Actions output variables.

    python3 tools/ci/data_age.py >> "$GITHUB_OUTPUT"

Used by the freshness workflow to decide whether to open a staleness issue. An
outbreak page that quietly goes stale is the main failure mode for this project:
the numbers still look authoritative, but they describe a situation that has
moved on.

Kept as a file rather than a heredoc in the workflow so it can be read and run
on its own - see tools/ci/build.sh for the general reasoning.
"""

import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

# Taken from the validator rather than restated. The validator fails the build
# at this threshold, which is what stops the site redeploying; a second copy of
# the number here could drift and have the warning arrive after the outage it is
# supposed to pre-empt.
sys.path.insert(0, str(ROOT / "tools"))
from validate import STALE_AFTER_DAYS  # noqa: E402


def main():
    doc = json.loads((ROOT / "data" / "outbreak.json").read_text(encoding="utf-8"))
    as_of = datetime.date.fromisoformat(doc["as_of"])
    age = (datetime.date.today() - as_of).days
    print(f"as_of={as_of}")
    print(f"days={age}")
    print(f"stale={'true' if age > STALE_AFTER_DAYS else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
