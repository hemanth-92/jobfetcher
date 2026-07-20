#!/usr/bin/env bash
# Daily jobfetcher run: only NEW jobs (seen history kept), re-analyze, print browse URL.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORKERS="${WORKERS:-6}"
OUTPUT_DIR="${OUTPUT_DIR:-results}"

echo "==> Jobfetcher daily run ($(date -Iseconds))"
echo "    workers=$WORKERS output_dir=$OUTPUT_DIR"
echo "    experience band from config.json (default 2–4 years)"

# Do NOT pass --reset-seen so previously seen URLs are skipped.
uv run jobfetcher --workers "$WORKERS" --output-dir "$OUTPUT_DIR"

HTML="$OUTPUT_DIR/jobs.html"
if [[ -f "$HTML" ]]; then
  echo
  echo "==> Browse report"
  echo "    file://$ROOT/$HTML"
  if command -v hostname >/dev/null 2>&1; then
    IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    if [[ -n "${IP:-}" ]]; then
      echo "    http://localhost:5500/$OUTPUT_DIR/jobs.html"
      echo "    http://${IP}:5500/$OUTPUT_DIR/jobs.html"
    fi
  fi
fi

echo "==> Done"
