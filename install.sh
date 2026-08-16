#!/usr/bin/env bash
# serp-sentry local installer: venv + deps + wizard + cron line.
# Uses uv (https://docs.astral.sh/uv/) when available; falls back to python3 -m venv + pip.
set -euo pipefail
cd "$(dirname "$0")"

echo "== serp-sentry installer =="

if command -v uv >/dev/null; then
  uv venv --quiet .venv
  uv pip install --quiet --python .venv/bin/python .
  echo "✓ installed into ./.venv (via uv)"
else
  if ! command -v python3 >/dev/null; then
    echo "Neither uv nor python3 found. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet .
  echo "✓ installed into ./.venv (via pip — consider installing uv, it's much faster)"
fi

if [ ! -f serp-sentry.yaml ]; then
  ./.venv/bin/serp-sentry init
else
  echo "✓ serp-sentry.yaml already exists — skipping wizard"
fi

./.venv/bin/serp-sentry doctor || true

BIN="$(pwd)/.venv/bin/serp-sentry"
echo
echo "To run the weekly rank check, add this to 'crontab -e':"
echo "  0 7 * * 1 cd $(pwd) && $BIN run >> $(pwd)/serp-sentry.log 2>&1"
echo
echo "Or push this repo to GitHub, add the LLM_API_KEY secret, and enable the"
echo "included Actions workflow — drafts get committed into the repo."
