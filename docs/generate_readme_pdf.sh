#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
README_PATH="$REPO_ROOT/README.md"
OUTPUT_PATH="$REPO_ROOT/docs/ReVive-README.pdf"
TEMP_HTML="$(mktemp /tmp/revive-readme-XXXXXX.html)"

cleanup() {
  rm -f "$TEMP_HTML"
}
trap cleanup EXIT

if ! command -v pandoc >/dev/null 2>&1; then
  echo "Error: pandoc is required to generate the PDF." >&2
  exit 1
fi

if ! command -v chromium >/dev/null 2>&1; then
  echo "Error: chromium is required to generate the PDF." >&2
  exit 1
fi

cd "$REPO_ROOT"

pandoc \
  "$README_PATH" \
  --from=gfm \
  --to=html5 \
  --standalone \
  --metadata "title=ReVive: Rethinking Vacant Spaces" \
  --resource-path="$REPO_ROOT" \
  --embed-resources \
  --output "$TEMP_HTML"

chromium \
  --headless \
  --disable-gpu \
  --no-sandbox \
  --print-to-pdf="$OUTPUT_PATH" \
  "file://$TEMP_HTML"

echo "Generated $OUTPUT_PATH"
