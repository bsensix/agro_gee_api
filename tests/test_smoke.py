import ast
from pathlib import Path

from fastapi.testclient import TestClient

from agro_gee_api.main import app

ACTIVE_RUNTIME_MODULES = (
    "agro_gee_api.routes.gee",
    "agro_gee_api.routes._authz",
)
FORBIDDEN_IMPORTS = ("agro_gee_api.db",)


def _get_module_path(module_name: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    return root.joinpath(*module_name.split(".")).with_suffix(".py")


def _read_imported_modules(path: Path) -> set[str]:
    imported_modules: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)
    return imported_modules


def _is_forbidden_import(import_name: str) -> bool:
    return any(
        import_name == forbidden or import_name.startswith(f"{forbidden}.")
        for forbidden in FORBIDDEN_IMPORTS
    )


def test_healthcheck_returns_200() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_active_runtime_routes_do_not_import_legacy_db_modules() -> None:
    for module_name in ACTIVE_RUNTIME_MODULES:
        imported_modules = _read_imported_modules(_get_module_path(module_name))
        forbidden_imports = sorted(
            module for module in imported_modules if _is_forbidden_import(module)
        )
        assert forbidden_imports == [], (
            f"{module_name} imports legacy db modules: {forbidden_imports}"
        )
