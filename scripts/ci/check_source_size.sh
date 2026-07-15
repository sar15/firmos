#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"

oversized="$(
  find apps/web/src firmos-backend apps/firmos-agent/src \
    apps/firmos-agent/src-tauri/src scripts \
    -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.rs' \) \
    -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/target/*' \
    -print0 \
  | xargs -0 wc -l \
  | awk '$2 != "total" && $1 > 300 {print}'
)"

if [[ -n "$oversized" ]]; then
  echo "Source files must remain at or below 300 lines:" >&2
  echo "$oversized" >&2
  exit 1
fi

echo "All source files are at or below 300 lines."
