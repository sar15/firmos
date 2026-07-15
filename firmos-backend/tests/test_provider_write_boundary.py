"""Routes and LangGraph nodes cannot import provider write functions."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {"create_bill", "create_invoice", "create_contact", "update_contact", "post_voucher"}
FORBIDDEN_CALLS = {"execute_action", "execute_write"}
SCOPES = (ROOT / "api/routes", ROOT / "workflows")


def _write_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("connectors."):
            violations.extend(f"{path.relative_to(ROOT)}:{name.name}" for name in node.names if name.name in FORBIDDEN)
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                node.func.id if isinstance(node.func, ast.Name) else ""
            )
            if name in FORBIDDEN_CALLS:
                violations.append(f"{path.relative_to(ROOT)}:{name}")
    return violations


def test_routes_and_workflows_do_not_import_provider_writes():
    violations = [violation for scope in SCOPES for path in scope.rglob("*.py") for violation in _write_imports(path)]
    assert not violations, "Provider writes must run only in approved worker executors:\n" + "\n".join(violations)
