#!/usr/bin/env bash
# What CI runs before publishing to Pages: rebuild from data/ rather than
# trusting the committed output, then validate, so a page that fails its own
# disclaimer and citation checks never gets served.
#
# See tools/ci/build.sh for why this is a script rather than steps in the YAML.
set -euo pipefail

python3 build.py
python3 tools/validate.py
