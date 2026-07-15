#!/usr/bin/env bash
set -euo pipefail

base_ref="${1:-${BASE_REF:-HEAD~1}}"
if ! git cat-file -e "$base_ref^{commit}" 2>/dev/null; then
  if git rev-parse --verify --quiet HEAD^ >/dev/null; then
    echo "Cannot find base revision: $base_ref" >&2
    exit 2
  fi
  echo "Initial commit has no earlier revision; duplicate-abstraction diff check skipped."
  exit 0
fi

added_lines() {
  git diff --unified=0 "$base_ref...HEAD" -- "$@" | grep '^+' | grep -v '^+++' || true
}

reject() {
  local message="$1"
  local matches="$2"
  if [[ -n "$matches" ]]; then
    echo "$message" >&2
    echo "$matches" >&2
    exit 1
  fi
}

reject "Use the approved paise conversion seam; do not add a local money converter." \
  "$(added_lines firmos-backend | grep -Ei '^[+][[:space:]]*(async[[:space:]]+)?def[[:space:]]+.*(paise|money|rupee|cents|minor_unit|minor_amount|convert_.*amount)' || true)"
reject "Do not add direct httpx.AsyncClient usage to Zoho request methods." \
  "$(added_lines firmos-backend/connectors/zoho_books | grep -E 'httpx.AsyncClient|from httpx import .*AsyncClient' || true)"
reject "Routes and workflows cannot import a provider write directly." \
  "$(added_lines firmos-backend/api/routes firmos-backend/workflows | grep -E '^\+[[:space:]]*(from[[:space:]]+connectors\.|import[[:space:]]+connectors\.)' || true)"
reject "Production paths cannot add mock, fake or dummy identifiers." \
  "$(added_lines firmos-backend/api firmos-backend/core firmos-backend/connectors firmos-backend/extraction firmos-backend/engines firmos-backend/workflows firmos-backend/models | grep -Ei '(mock_|fake_|dummy_|Mock[A-Z]|Fake[A-Z]|Dummy[A-Z])' || true)"

echo "No duplicate abstractions introduced."
