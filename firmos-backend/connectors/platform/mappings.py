"""Versioned connector mappings; suggestions never mutate provider masters."""
from dataclasses import dataclass


@dataclass(frozen=True)
class MappingSuggestion:
    provider_id: str
    normalized_name: str
    confidence: float


def suggest_exact(name: str, candidates: list[dict]) -> list[MappingSuggestion]:
    normalized = " ".join(name.casefold().split())
    return [MappingSuggestion(str(c["provider_id"]), normalized, 1.0) for c in candidates
            if " ".join(str(c.get("name", "")).casefold().split()) == normalized]


async def approve_mapping(conn, *, firm_id: str, installation_id: str, mapping_type: str,
                          internal_id: str, provider_id: str, approved_by: str) -> None:
    await conn.execute(
        "UPDATE connector_mappings SET active=false WHERE installation_id=$1 AND mapping_type=$2 AND internal_id=$3 AND active",
        installation_id, mapping_type, internal_id,
    )
    await conn.execute(
        """INSERT INTO connector_mappings(firm_id,installation_id,mapping_type,internal_id,provider_id,source,confidence,approved_by,approved_at)
           VALUES($1,$2,$3,$4,$5,'MANUAL',1,$6,NOW())""",
        firm_id, installation_id, mapping_type, internal_id, provider_id, approved_by,
    )
