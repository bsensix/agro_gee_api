from pathlib import Path
import tomllib


def test_setuptools_package_discovery_is_explicit_for_api_only() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    content = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    include = (
        content.get("tool", {})
        .get("setuptools", {})
        .get("packages", {})
        .get("find", {})
        .get("include", [])
    )

    assert include == ["agro_gee_api*"]


def test_dev_dependencies_include_httpx_for_fastapi_testclient() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    content = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    dev_dependencies = (
        content.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    )

    assert any(dependency.startswith("httpx") for dependency in dev_dependencies)


def test_dev_dependencies_include_httpx2_for_starlette_testclient() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    content = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    dev_dependencies = (
        content.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    )

    assert any(dependency.startswith("httpx2") for dependency in dev_dependencies)
