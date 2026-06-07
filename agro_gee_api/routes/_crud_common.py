from typing import Any

import psycopg
from fastapi import HTTPException


INVALID_GEOMETRY_CRS_MESSAGE = "Invalid geometry CRS; only EPSG:4326 is supported"


def _coerce_crs_name(crs: Any) -> str | None:
    if isinstance(crs, str):
        return crs
    if not isinstance(crs, dict):
        return None

    properties = crs.get("properties")
    if isinstance(properties, dict):
        name = properties.get("name")
        if isinstance(name, str):
            return name

        code = properties.get("code")
        if isinstance(code, int):
            return f"EPSG:{code}"
        if isinstance(code, str):
            return code

    return None


def _is_epsg_4326(crs: Any) -> bool:
    crs_name = _coerce_crs_name(crs)
    if crs_name is None:
        return False

    normalized = crs_name.strip().lower()
    return normalized in {
        "4326",
        "epsg:4326",
        "urn:ogc:def:crs:epsg::4326",
        "http://www.opengis.net/def/crs/epsg/0/4326",
    }


def ensure_geojson_payload(geometry: Any) -> None:
    if not isinstance(geometry, dict):
        raise HTTPException(status_code=400, detail="Invalid geometry payload")
    if "type" not in geometry or "coordinates" not in geometry:
        raise HTTPException(status_code=400, detail="Invalid geometry payload")

    if "crs" in geometry and not _is_epsg_4326(geometry.get("crs")):
        raise HTTPException(status_code=400, detail=INVALID_GEOMETRY_CRS_MESSAGE)


def raise_bad_request_for_known_db_error(exc: psycopg.Error) -> None:
    state = exc.sqlstate or ""
    message = str(exc).lower()
    if "geojson" in message or "geometry" in message:
        raise HTTPException(status_code=400, detail="Invalid geometry payload") from exc
    if state == "23505":
        raise HTTPException(status_code=409, detail="Resource already exists") from exc
    if state == "23503":
        raise HTTPException(
            status_code=400, detail="Referenced resource not found"
        ) from exc
    if state.startswith("22"):
        raise HTTPException(status_code=400, detail="Invalid request data") from exc
    if state in {"23502", "23514"}:
        raise HTTPException(status_code=400, detail="Invalid request data") from exc
    if state.startswith("23"):
        raise HTTPException(status_code=400, detail="Invalid request data") from exc
