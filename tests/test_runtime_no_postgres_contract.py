import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

ACTIVE_RUNTIME_MODULES = [
    REPO_ROOT / "agro_gee_api" / "main.py",
    REPO_ROOT / "agro_gee_api" / "routes" / "auth.py",
    REPO_ROOT / "agro_gee_api" / "routes" / "analytics.py",
    REPO_ROOT / "agro_gee_api" / "routes" / "gee.py",
    REPO_ROOT / "agro_gee_api" / "routes" / "_authz.py",
    REPO_ROOT / "agro_gee_api" / "services" / "gee_catalog.py",
    REPO_ROOT / "agro_gee_api" / "services" / "gee_client.py",
    REPO_ROOT / "agro_gee_api" / "services" / "gee_meteo_catalog.py",
    REPO_ROOT / "agro_gee_api" / "services" / "gee_meteo_extract.py",
    REPO_ROOT / "agro_gee_api" / "services" / "gee_runtime.py",
    REPO_ROOT / "agro_gee_api" / "services" / "gee_sentinel2.py",
    REPO_ROOT / "agro_gee_api" / "services" / "gee_sentinel2_extract.py",
]


def _has_forbidden_import(module_path: Path) -> bool:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "psycopg" or name.startswith("psycopg."):
                    return True
                if name == "agro_gee_api.db" or name.startswith("agro_gee_api.db."):
                    return True

        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name == "psycopg" or module_name.startswith("psycopg."):
                return True
            if module_name == "agro_gee_api.db" or module_name.startswith(
                "agro_gee_api.db."
            ):
                return True

    return False


def test_runtime_dependency_excludes_psycopg() -> None:
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "psycopg" not in pyproject_text


def test_docker_compose_default_api_flow_has_no_mandatory_db_dependency() -> None:
    compose_text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "depends_on" not in compose_text
    assert "POSTGRES_HOST" not in compose_text


def test_docker_compose_does_not_define_db_service() -> None:
    compose_text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "\n  db:\n" not in compose_text


def test_api_dockerfile_runtime_does_not_install_psycopg() -> None:
    dockerfile_text = (
        REPO_ROOT / "infrastructure" / "docker" / "api.Dockerfile"
    ).read_text(encoding="utf-8")
    assert "psycopg" not in dockerfile_text


def test_env_example_does_not_define_postgres_baseline_variables() -> None:
    env_text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "POSTGRES_DB=" not in env_text
    assert "POSTGRES_USER=" not in env_text
    assert "POSTGRES_PASSWORD=" not in env_text
    assert "POSTGRES_PORT=" not in env_text


def test_active_runtime_modules_do_not_import_psycopg_or_db_module() -> None:
    offending_modules = [
        str(path.relative_to(REPO_ROOT))
        for path in ACTIVE_RUNTIME_MODULES
        if _has_forbidden_import(path)
    ]
    assert offending_modules == []
