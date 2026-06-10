from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from agro_gee_api.routes.analytics import router as analytics_router
from agro_gee_api.routes.auth import router as auth_router
from agro_gee_api.routes.gee import router as gee_router

OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "Authentication and authorization endpoints.",
    },
    {
        "name": "analytics",
        "description": "Analytics and reporting endpoints.",
    },
    {
        "name": "gee-core",
        "description": "Core Google Earth Engine health, auth, and dataset catalog endpoints.",
    },
    {
        "name": "sentinel2",
        "description": "Sentinel-2 extraction endpoints for point and polygon geometries.",
    },
    {
        "name": "era5-land",
        "description": "ERA5-Land extraction and variable catalog endpoints.",
    },
    {
        "name": "ifs-forecast",
        "description": "IFS forecast extraction and variable catalog endpoints.",
    },
    {
        "name": "satellite-embedding-annual",
        "description": "Satellite Embedding Annual extraction and variable catalog endpoints.",
    },
]

app = FastAPI(title="Agro Insight API", openapi_tags=OPENAPI_TAGS)

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DIST_DIR = REPO_ROOT / "web" / "dist"

app.include_router(auth_router)
app.include_router(gee_router)
app.include_router(analytics_router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


def _spa_index_path() -> Path:
    index_path = WEB_DIST_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="Web app not built")
    return index_path


def _spa_asset_path(asset_path: str) -> Path:
    assets_dir = (WEB_DIST_DIR / "assets").resolve()
    requested_path = (assets_dir / asset_path).resolve()

    try:
        requested_path.relative_to(assets_dir)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not Found") from exc

    if not requested_path.is_file():
        raise HTTPException(status_code=404, detail="Not Found")

    return requested_path


@app.get("/assets/{asset_path:path}")
def serve_web_asset(asset_path: str) -> FileResponse:
    return FileResponse(_spa_asset_path(asset_path))


@app.get("/app")
def serve_web_app() -> FileResponse:
    return FileResponse(_spa_index_path())


@app.get("/app/{path:path}")
def serve_web_app_fallback(path: str) -> FileResponse:  # noqa: ARG001
    return FileResponse(_spa_index_path())
