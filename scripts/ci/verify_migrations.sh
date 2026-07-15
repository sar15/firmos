#!/usr/bin/env bash
set -euo pipefail

database_url="${1:?usage: verify_migrations.sh postgresql://.../postgres}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
snapshot="$root/supabase/schema-snapshots/20260626000000_platform_prerequisites.sql"
migrations="$root/supabase/migrations"
baseline="20260712000008_private_bank_evidence.sql"
base_url="${database_url%/postgres}"

reset_database() {
  local name="$1"
  psql "$database_url" -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $name WITH (FORCE)"
  psql "$database_url" -v ON_ERROR_STOP=1 -c "CREATE DATABASE $name"
}

apply_file() {
  psql "$1" -v ON_ERROR_STOP=1 -f "$2" >/dev/null
}

apply_migrations() {
  local url="$1"
  local phase="$2"
  for migration in "$migrations"/*.sql; do
    local name
    name="$(basename "$migration")"
    if [[ "$phase" == "baseline" && "$name" > "$baseline" ]]; then
      continue
    fi
    if [[ "$phase" == "after-baseline" ]] && [[ "$name" < "$baseline" || "$name" == "$baseline" ]]; then
      continue
    fi
    apply_file "$url" "$migration"
  done
}

reset_database firmos_migration_fresh
fresh_url="$base_url/firmos_migration_fresh"
apply_file "$fresh_url" "$snapshot"
apply_migrations "$fresh_url" all

reset_database firmos_migration_upgrade
upgrade_url="$base_url/firmos_migration_upgrade"
apply_file "$upgrade_url" "$snapshot"
apply_migrations "$upgrade_url" baseline
apply_migrations "$upgrade_url" after-baseline

echo "Fresh and upgrade migration paths passed."
