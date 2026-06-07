import json
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from agro_gee_api.db import get_connection
from agro_gee_api.routes._authz import AuthzContext, get_authz_context
from agro_gee_api.routes._crud_common import (
    ensure_geojson_payload,
    raise_bad_request_for_known_db_error,
)


class FarmCreate(BaseModel):
    user_id: int
    name: str
    geometry: dict[str, Any]


class FarmUpdate(BaseModel):
    user_id: int
    name: str
    geometry: dict[str, Any]


class FarmRead(BaseModel):
    farm_id: int
    user_id: int
    name: str
    geometry: dict[str, Any]
    area_ha: str


router = APIRouter(prefix="/farms", tags=["farms"])


def _raise_forbidden_if_farm_exists(*, farm_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM core.farms WHERE farm_id = %s;", (farm_id,))
            exists = cur.fetchone() is not None
    if exists:
        raise HTTPException(status_code=403, detail="Forbidden")


def _is_existing_user(user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM core.users WHERE user_id = %s;", (user_id,))
            return cur.fetchone() is not None


@router.post("", response_model=FarmRead, status_code=status.HTTP_201_CREATED)
def create_farm(
    payload: FarmCreate,
    authz: AuthzContext = Depends(get_authz_context),
) -> FarmRead:
    ensure_geojson_payload(payload.geometry)
    if payload.user_id not in authz.allowed_user_ids and _is_existing_user(
        payload.user_id
    ):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH input_geom AS (
                        SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) AS geom
                    ), validated_geom AS (
                        SELECT ST_Multi(geom) AS geom
                        FROM input_geom
                        WHERE ST_IsValid(geom)
                          AND ST_GeometryType(geom) IN ('ST_Polygon', 'ST_MultiPolygon')
                    )
                    INSERT INTO core.farms (user_id, name, geometry, area_ha)
                    SELECT %s,
                           %s,
                           geom,
                           ST_Area(geom::geography) / 10000.0
                    FROM validated_geom
                    RETURNING farm_id, user_id, name,
                              ST_AsGeoJSON(geometry)::json AS geometry,
                              area_ha::text AS area_ha;
                    """,
                    (
                        json.dumps(payload.geometry),
                        payload.user_id,
                        payload.name,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(
                        status_code=400, detail="Invalid geometry payload"
                    )
                conn.commit()
    except psycopg.Error as exc:
        raise_bad_request_for_known_db_error(exc)
        raise
    return FarmRead.model_validate(row)


@router.get("", response_model=list[FarmRead])
def list_farms(authz: AuthzContext = Depends(get_authz_context)) -> list[FarmRead]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT farm_id, user_id, name,
                       ST_AsGeoJSON(geometry)::json AS geometry,
                       area_ha::text AS area_ha
                FROM core.farms
                WHERE user_id = ANY(%s::bigint[])
                ORDER BY farm_id;
                """,
                (list(authz.allowed_user_ids),),
            )
            rows = cur.fetchall()
    return [FarmRead.model_validate(row) for row in rows]


@router.get("/{farm_id}", response_model=FarmRead)
def get_farm(
    farm_id: int,
    authz: AuthzContext = Depends(get_authz_context),
) -> FarmRead:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT farm_id, user_id, name,
                       ST_AsGeoJSON(geometry)::json AS geometry,
                       area_ha::text AS area_ha
                FROM core.farms
                WHERE farm_id = %s
                  AND user_id = ANY(%s::bigint[]);
                """,
                (farm_id, list(authz.allowed_user_ids)),
            )
            row = cur.fetchone()
    if row is None:
        _raise_forbidden_if_farm_exists(farm_id=farm_id)
        raise HTTPException(status_code=404, detail="Farm not found")
    return FarmRead.model_validate(row)


@router.put("/{farm_id}", response_model=FarmRead)
def update_farm(
    farm_id: int,
    payload: FarmUpdate,
    authz: AuthzContext = Depends(get_authz_context),
) -> FarmRead:
    ensure_geojson_payload(payload.geometry)
    if payload.user_id not in authz.allowed_user_ids and _is_existing_user(
        payload.user_id
    ):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH input_geom AS (
                        SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) AS geom
                    ), validated_geom AS (
                        SELECT ST_Multi(geom) AS geom
                        FROM input_geom
                        WHERE ST_IsValid(geom)
                          AND ST_GeometryType(geom) IN ('ST_Polygon', 'ST_MultiPolygon')
                    )
                    UPDATE core.farms
                    SET user_id = %s,
                        name = %s,
                        geometry = validated_geom.geom,
                        area_ha = ST_Area(validated_geom.geom::geography) / 10000.0
                    FROM validated_geom
                    WHERE farm_id = %s
                      AND user_id = ANY(%s::bigint[])
                    RETURNING farm_id, user_id, name,
                              ST_AsGeoJSON(geometry)::json AS geometry,
                              area_ha::text AS area_ha;
                    """,
                    (
                        json.dumps(payload.geometry),
                        payload.user_id,
                        payload.name,
                        farm_id,
                        list(authz.allowed_user_ids),
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        "SELECT user_id FROM core.farms WHERE farm_id = %s;",
                        (farm_id,),
                    )
                    farm_row = cur.fetchone()
                    if farm_row is None:
                        raise HTTPException(status_code=404, detail="Farm not found")
                    if int(farm_row["user_id"]) not in authz.allowed_user_ids:
                        raise HTTPException(status_code=403, detail="Forbidden")
                    raise HTTPException(
                        status_code=400, detail="Invalid geometry payload"
                    )
                conn.commit()
    except psycopg.Error as exc:
        raise_bad_request_for_known_db_error(exc)
        raise
    return FarmRead.model_validate(row)


@router.delete("/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farm(
    farm_id: int,
    authz: AuthzContext = Depends(get_authz_context),
) -> Response:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM core.farms
                    WHERE farm_id = %s
                      AND user_id = ANY(%s::bigint[]);
                    """,
                    (farm_id, list(authz.allowed_user_ids)),
                )
                deleted = cur.rowcount
                conn.commit()
    except psycopg.Error as exc:
        raise_bad_request_for_known_db_error(exc)
        raise
    if deleted == 0:
        _raise_forbidden_if_farm_exists(farm_id=farm_id)
        raise HTTPException(status_code=404, detail="Farm not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
