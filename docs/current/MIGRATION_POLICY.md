# Migration policy

## Rules

1. A migration under `supabase/migrations/` is immutable once applied anywhere shared.
2. Use `YYYYMMDDHHMMSS_<task_id_lowercase>_<description>.sql`; the timestamp must be unique and sortable.
3. Never use a route or model as schema documentation. Read the full migration history and the latest relevant tables first.
4. Correct a released migration with a new forward migration. Roll back application code when safe; do not rewrite migration history.
5. Every schema change names its source-of-truth table, RLS impact, backfill plan and forward-fix path in its task/PR description.

## Verification

`scripts/ci/verify_migrations.sh` validates two paths against the pinned platform prerequisite snapshot:

- a fresh database applies every migration in order;
- an upgrade database applies migrations through `20260712000008_private_bank_evidence.sql`, then every later migration.

The prerequisite snapshot is CI-only. It represents Supabase roles, storage tables and LangGraph checkpoint tables that are provisioned outside this repository's migration history. It is not a production migration and must not be applied to a hosted project.

## Operational recovery

- A migration that is not yet deployed may be replaced before merge.
- A deployed migration is repaired with a new migration and an explicit data correction where needed.
- A failed deployment is rolled forward unless application rollback leaves the schema safely compatible.
- A migration that needs a destructive data operation requires a backup, dry-run query, owner approval and a documented recovery command.
