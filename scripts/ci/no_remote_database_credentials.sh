#!/usr/bin/env bash
set -euo pipefail

matches="$(git grep -nEI 'postgres(ql)?://[^:/[:space:]]+:[^@[:space:]]+@' -- ':!*.lock' || true)"
remote_matches="$(printf '%s\n' "$matches" | grep -Ev '@(localhost|127\.0\.0\.1|postgres)(:|/)' || true)"

if [[ -n "$remote_matches" ]]; then
  echo "Remote database credentials must not be committed:" >&2
  echo "$remote_matches" >&2
  exit 1
fi

echo "No remote database credentials found."
