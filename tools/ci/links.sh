#!/usr/bin/env bash
# What CI runs to check that every cited source resolves and still says what we
# say it says. Advisory: the job is continue-on-error, because a dead link is
# worth knowing about but must not block shipping a correction to health
# information.
#
# See tools/ci/build.sh for why this is a script rather than steps in the YAML.
set -euo pipefail

# Reading the two cited PDFs needs pypdf. Without it those claims are skipped
# rather than guessed at, so this failing is survivable - but it should be loud.
echo "::group::Install the PDF reader"
pip install --quiet --disable-pip-version-check -r requirements.txt \
  || echo "::warning::pypdf did not install; PDF-backed claims will be skipped"
echo "::endgroup::"

python3 tools/check_links.py
