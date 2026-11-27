#!/usr/bin/env bash
# Runs every test suite: the API (pytest) and the dashboard proxy (node).
#
#   scripts/test.sh                      # starts a throwaway Postgres 16 with Docker
#   PYTHON=/path/to/python scripts/test.sh
#   TEST_DATABASE_URL=... scripts/test.sh   # use an empty *_test database instead
#
# Install first: python -m pip install -r requirements-dev.txt
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${PYTHON:-}" ]; then
  if [ -x .venv/bin/python ]; then PYTHON=.venv/bin/python; else PYTHON=python3; fi
fi

status=0

echo "== API tests"
"$PYTHON" -m pytest || status=1

echo "== Dashboard tests"
(
  cd src/dashboard
  # set -e does not apply inside a subshell followed by ||, so stop explicitly
  if [ ! -d node_modules ]; then npm ci || exit 1; fi
  npm test
) || status=1

exit "$status"
