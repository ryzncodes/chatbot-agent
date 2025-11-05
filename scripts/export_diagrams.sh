#!/usr/bin/env bash
set -euo pipefail

# Export Mermaid diagrams to SVG/PNG using mermaid-cli (mmdc).
# Requires Node.js. Installs mermaid-cli locally if not present.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIAGRAM_DIR="$ROOT_DIR/docs/diagrams"

MMDC_BIN="$(command -v mmdc || true)"

if [[ -z "$MMDC_BIN" ]]; then
  echo "mermaid-cli (mmdc) not found; attempting to install locally via npx..." >&2
  # Use npx to execute without global install. Requires internet access.
  MMDC_CMD=(npx @mermaid-js/mermaid-cli@10.9.1 -t default)
else
  MMDC_CMD=("$MMDC_BIN")
fi

mkdir -p "$DIAGRAM_DIR"

render() {
  local input="$1"; shift
  local base
  base="${input%.mmd}"
  echo "Rendering $input → ${base}.svg and ${base}.png"
  "${MMDC_CMD[@]}" -i "$input" -o "${base}.svg"
  "${MMDC_CMD[@]}" -i "$input" -o "${base}.png"
}

render "$DIAGRAM_DIR/system-architecture.mmd"
render "$DIAGRAM_DIR/planner-sequence.mmd"

echo "Done. Outputs in $DIAGRAM_DIR"

