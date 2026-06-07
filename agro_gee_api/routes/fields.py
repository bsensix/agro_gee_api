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


class FieldCreate(BaseModel):
    farm_id: int
    name: str
    geometry: dict[str, Any]


class FieldUpdate(BaseModel):
    farm_id: int
    name: str
    geometry: dict[str, Any]


class FieldRead(BaseModel):
    field_id: int
    farm_id: int
    name: str
    geometry: dict[str, Any]
    area_ha: str


router = APIRouter(prefix="/fields", tags=["fields"])


def _raise_forbidden_if_field_exists(*, field_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM core.fields WHERE field_id = %s;", (field_id,))
            exists = cur.fetchone() is not None
    if exists:
        raise HTTPException(status_code=403, detail="Forbidden")


def _farm_owner_user_id(*, farm_id: int) -> int | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM core.farms WHERE farm_id = %s;", (farm_id,)
            )
            row = cur.fetchone()
    if row is None:
        return None
    return int(row["user_id"])


@router.post("", response_model=FieldRead, status_code=status.HTTP_201_CREATED)
def create_field(
    payload: FieldCreate,
    authz: AuthzContext = Depends(get_authz_context),
) -> FieldRead:
    ensure_geojson_payload(payload.geometry)
    owner_user_id = _farm_owner_user_id(farm_id=payload.farm_id)
    if owner_user_id is not None and owner_user_id not in authz.allowed_user_ids:
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
                    INSERT INTO core.fields (farm_id, name, geometry, area_ha)
                    SELECT %s,
                           %s,
                           geom,
                           ST_Area(geom::geography) / 10000.0
                    FROM validated_geom
                    RETURNING field_id, farm_id, name,
                              ST_AsGeoJSON(geometry)::json AS geometry,
                              area_ha::text AS area_ha;
                    """,
                    (
                        json.dumps(payload.geometry),
                        payload.farm_id,
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
    return FieldRead.model_validate(row)


@router.get("", response_model=list[FieldRead])
def list_fields(authz: AuthzContext = Depends(get_authz_context)) -> list[FieldRead]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT f.field_id, f.farm_id, f.name,
                       ST_AsGeoJSON(f.geometry)::json AS geometry,
                       f.area_ha::text AS area_ha
                FROM core.fields AS f
                JOIN core.farms AS fa ON fa.farm_id = f.farm_id
                WHERE fa.user_id = ANY(%s::bigint[])
                ORDER BY field_id;
                """,
                (list(authz.allowed_user_ids),),
            )
            rows = cur.fetchall()
    return [FieldRead.model_validate(row) for row in rows]


@router.get("/{field_id}", response_model=FieldRead)
def get_field(
    field_id: int,
    authz: AuthzContext = Depends(get_authz_context),
) -> FieldRead:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT f.field_id, f.farm_id, f.name,
                       ST_AsGeoJSON(f.geometry)::json AS geometry,
                       f.area_ha::text AS area_ha
                FROM core.fields AS f
                JOIN core.farms AS fa ON fa.farm_id = f.farm_id
                WHERE f.field_id = %s
                  AND fa.user_id = ANY(%s::bigint[]);
                """,
                (field_id, list(authz.allowed_user_ids)),
            )
            row = cur.fetchone()
    if row is None:
        _raise_forbidden_if_field_exists(field_id=field_id)
        raise HTTPException(status_code=404, detail="Field not found")
    return FieldRead.model_validate(row)


@router.put("/{field_id}", response_model=FieldRead)
def update_field(
    field_id: int,
    payload: FieldUpdate,
    authz: AuthzContext = Depends(get_authz_context),
) -> FieldRead:
    ensure_geojson_payload(payload.geometry)
    owner_user_id = _farm_owner_user_id(farm_id=payload.farm_id)
    if owner_user_id is not None and owner_user_id not in authz.allowed_user_ids:
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
                    UPDATE core.fields
                    SET farm_id = %s,
                        name = %s,
                        geometry = validated_geom.geom,
                        area_ha = ST_Area(validated_geom.geom::geography) / 10000.0
                    FROM validated_geom
                    WHERE field_id = %s
                      AND field_id IN (
                          SELECT f.field_id
                          FROM core.fields AS f
                          JOIN core.farms AS fa ON fa.farm_id = f.farm_id
                          WHERE fa.user_id = ANY(%s::bigint[])
                      )
                    RETURNING field_id, farm_id, name,
                              ST_AsGeoJSON(geometry)::json AS geometry,
                              area_ha::text AS area_ha;
                    """,
                    (
                        json.dumps(payload.geometry),
                        payload.farm_id,
                        payload.name,
                        field_id,
                        list(authz.allowed_user_ids),
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        """
                        SELECT f.field_id, fa.user_id
                        FROM core.fields AS f
                        JOIN core.farms AS fa ON fa.farm_id = f.farm_id
                        WHERE f.field_id = %s;
                        """,
                        (field_id,),
                    )
                    field_row = cur.fetchone()
                    if field_row is None:
                        raise HTTPException(status_code=404, detail="Field not found")
                    if int(field_row["user_id"]) not in authz.allowed_user_ids:
                        raise HTTPException(status_code=403, detail="Forbidden")
                    raise HTTPException(
                        status_code=400, detail="Invalid geometry payload"
                    )
                conn.commit()
    except psycopg.Error as exc:
        raise_bad_request_for_known_db_error(exc)
        raise
    return FieldRead.model_validate(row)


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(
    field_id: int,
    authz: AuthzContext = Depends(get_authz_context),
) -> Response:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM core.fields
                WHERE field_id = %s
                  AND field_id IN (
                      SELECT f.field_id
                      FROM core.fields AS f
                      JOIN core.farms AS fa ON fa.farm_id = f.farm_id
                      WHERE fa.user_id = ANY(%s::bigint[])
                  );
                """,
                (field_id, list(authz.allowed_user_ids)),
            )
            deleted = cur.rowcount
            conn.commit()
    if deleted == 0:
        _raise_forbidden_if_field_exists(field_id=field_id)
        raise HTTPException(status_code=404, detail="Field not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
