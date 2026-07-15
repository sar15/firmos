"""Verify that the committed web API contract matches FastAPI's OpenAPI schema."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "firmos-backend"
SNAPSHOT = ROOT / "apps/web/src/lib/api/generated/openapi.json"
WEB_API_FILES = ROOT / "apps/web/src/features"


def load_schema() -> dict:
    sys.path.insert(0, str(BACKEND))
    from api.main import app

    return app.openapi()


def normalise_path(path: str) -> str:
    path = path.split("?", 1)[0]
    return re.sub(r"\$\{[^}]+\}", "{value}", path)


def path_exists(path: str, schema_paths: set[str]) -> bool:
    return any(
        re.fullmatch(re.sub(r"\{[^}]+\}", r"[^/]+", schema_path), path)
        for schema_path in schema_paths
    )


def validate_web_paths(schema: dict) -> list[str]:
    errors: list[str] = []
    schema_paths = set(schema["paths"])
    pattern = re.compile(r"fetch\(\s*[`\"](?P<path>/api/[^`\"]+)[`\"]", re.DOTALL)
    for api_file in WEB_API_FILES.rglob("*.api.ts"):
        for match in pattern.finditer(api_file.read_text()):
            path = normalise_path(match.group("path"))
            if not path_exists(path, schema_paths):
                errors.append(f"{api_file.relative_to(ROOT)}: unknown backend path {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="refresh the committed OpenAPI snapshot")
    args = parser.parse_args()

    schema = load_schema()
    rendered = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    if args.write:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(rendered)
    elif not SNAPSHOT.exists() or SNAPSHOT.read_text() != rendered:
        print("OpenAPI contract changed. Run: python3 firmos-backend/scripts/check_openapi_contract.py --write")
        return 1

    errors = validate_web_paths(schema)
    if errors:
        print("Frontend API paths missing from FastAPI OpenAPI:")
        print("\n".join(errors))
        return 1
    print("OpenAPI contract is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
