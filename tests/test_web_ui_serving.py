from pathlib import Path

from fastapi.testclient import TestClient

from agro_gee_api.main import app
import agro_gee_api.main as main_module


def _write_dist(tmp_path: Path) -> Path:
    dist_dir = tmp_path / "web" / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<html><body>SPA</body></html>", encoding="utf-8"
    )
    return dist_dir


def test_app_returns_html_when_dist_exists(tmp_path: Path, monkeypatch) -> None:
    dist_dir = _write_dist(tmp_path)
    monkeypatch.setattr(main_module, "WEB_DIST_DIR", dist_dir)

    client = TestClient(app)
    response = client.get("/app")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "SPA" in response.text


def test_app_nested_path_falls_back_to_index_html(tmp_path: Path, monkeypatch) -> None:
    dist_dir = _write_dist(tmp_path)
    monkeypatch.setattr(main_module, "WEB_DIST_DIR", dist_dir)

    client = TestClient(app)
    response = client.get("/app/users")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "SPA" in response.text


def test_app_nested_path_returns_404_when_dist_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(main_module, "WEB_DIST_DIR", tmp_path / "web" / "dist")

    client = TestClient(app)
    response = client.get("/app/users")

    assert response.status_code == 404
    assert response.json() == {"detail": "Web app not built"}


def test_assets_returns_404_when_assets_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main_module, "WEB_DIST_DIR", tmp_path / "web" / "dist")

    client = TestClient(app)
    response = client.get("/assets/app.js")

    assert response.status_code == 404


def test_assets_serves_file_without_restart_after_assets_appear(
    tmp_path: Path, monkeypatch
) -> None:
    dist_dir = tmp_path / "web" / "dist"
    assets_dir = dist_dir / "assets"
    dist_dir.mkdir(parents=True)
    monkeypatch.setattr(main_module, "WEB_DIST_DIR", dist_dir)

    client = TestClient(app)

    missing_response = client.get("/assets/app.js")
    assert missing_response.status_code == 404

    assets_dir.mkdir(parents=True)
    (assets_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")

    served_response = client.get("/assets/app.js")
    assert served_response.status_code == 200
    assert "javascript" in served_response.headers["content-type"]
    assert "console.log('ok');" in served_response.text
