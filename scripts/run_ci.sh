#!/usr/bin/env bash
set -euo pipefail

# Resolve repository root from script location.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Backend checks =="
pushd "${ROOT_DIR}/backend" >/dev/null

poetry install
poetry run ruff check .
poetry run black --check .
PYTHONPATH="${ROOT_DIR}" poetry run pytest ../tests --cov=backend --cov-report=term --cov-report=xml
poetry run python ../scripts/export_openapi.py

popd >/dev/null

echo "== Frontend checks =="
pushd "${ROOT_DIR}/frontend" >/dev/null

npm install
npm run lint
npm run build

popd >/dev/null
