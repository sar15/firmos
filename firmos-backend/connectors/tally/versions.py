"""Release claims for Tally are deny-by-default until a real certification record exists."""

# Add an exact value returned by $$Version only after TA-026 passes on that release.
CERTIFIED_TALLY_VERSIONS: frozenset[str] = frozenset()
MINIMUM_SECURE_AGENT_VERSION = "1.0.0"


def version_support(version: str) -> dict[str, bool]:
    certified = version.strip() in CERTIFIED_TALLY_VERSIONS
    return {"xml_read": certified, "xml_write": certified, "json_read": False, "json_write": False}


def agent_version_supported(version: str) -> bool:
    try:
        current = tuple(int(part) for part in version.split("."))
        minimum = tuple(int(part) for part in MINIMUM_SECURE_AGENT_VERSION.split("."))
        return current >= minimum
    except ValueError:
        return False
