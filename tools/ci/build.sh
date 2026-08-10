#!/usr/bin/env bash
# What CI runs to build and check the site.
#
# The workflow that calls this is a fixed skeleton: checkout, pick a Python,
# run this file. Everything that changes over time lives here instead, where it
# can be edited like any other file in the repo. GitHub gates .github/workflows
# behind a separate permission, and round-tripping every CI change through a
# manual edit was costing more than it was protecting - the workflow already
# runs build.py and tools/validate.py, both of which are editable, so the step
# list was the only thing the gate was still holding.
#
# What stays in the YAML is what matters: which actions run, what permissions
# the job is granted, and which secrets it can see. Nothing here can widen any
# of those.
set -euo pipefail

echo "::group::Build the site"
python3 build.py
echo "::endgroup::"

# site/ is generated output and is committed so it can be served directly. If a
# data/ change lands without a rebuild, the published page silently disagrees
# with the data that is supposed to back it.
echo "::group::Check the committed site/ is not stale"
if ! git diff --exit-code -- site/; then
  echo "::error::site/ is out of date with data/. Run 'python3 build.py' and commit the result."
  exit 1
fi
echo "::endgroup::"

echo "::group::Validate data, citations, disclaimers and HTML"
python3 tools/validate.py
echo "::endgroup::"
