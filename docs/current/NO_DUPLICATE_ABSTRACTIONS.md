# No-duplicate-abstraction rule

Before adding a helper, search the repository map and callers. The approved seams are `get_settings()` for configuration, `paise()` for new provider-value conversion, `FinanceActionEngine` for accounting mutations, `AccountingPlugin` for connector capability and FastAPI routes as HTTP boundaries.

`scripts/ci/no_duplicate_abstractions.sh` rejects newly added production code that introduces local money converters, direct Zoho `httpx.AsyncClient()` usage, direct provider write imports in routes/workflows, or mock/fake/dummy production identifiers. It evaluates added lines only so the legacy baseline can be removed deliberately instead of being silently grandfathered into new work.
