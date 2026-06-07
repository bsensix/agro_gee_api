from datetime import datetime

import psycopg
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from agro_gee_api.db import get_connection
from agro_gee_api.routes._crud_common import raise_bad_request_for_known_db_error


class UserCreate(BaseModel):
    name: str
    email: str
    role: str
    parent_user_id: int | None = None


class UserUpdate(BaseModel):
    name: str
    email: str
    role: str
    parent_user_id: int | None = None


class UserRead(BaseModel):
    user_id: int
    parent_user_id: int | None
    name: str
    email: str
    role: str
    created_at: datetime


router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate) -> UserRead:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.users (parent_user_id, name, email, role)
                    VALUES (%s, %s, %s, %s)
                    RETURNING user_id, parent_user_id, name, email, role, created_at;
                    """,
                    (payload.parent_user_id, payload.name, payload.email, payload.role),
                )
                row = cur.fetchone()
                conn.commit()
    except psycopg.Error as exc:
        raise_bad_request_for_known_db_error(exc)
        raise
    return UserRead.model_validate(row)


@router.get("", response_model=list[UserRead])
def list_users() -> list[UserRead]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, parent_user_id, name, email, role, created_at
                FROM core.users
                ORDER BY user_id;
                """
            )
            rows = cur.fetchall()
    return [UserRead.model_validate(row) for row in rows]


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int) -> UserRead:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, parent_user_id, name, email, role, created_at
                FROM core.users
                WHERE user_id = %s;
                """,
                (user_id,),
            )
            row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(row)


@router.put("/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate) -> UserRead:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE core.users
                    SET parent_user_id = %s,
                        name = %s,
                        email = %s,
                        role = %s
                    WHERE user_id = %s
                    RETURNING user_id, parent_user_id, name, email, role, created_at;
                    """,
                    (
                        payload.parent_user_id,
                        payload.name,
                        payload.email,
                        payload.role,
                        user_id,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
    except psycopg.Error as exc:
        raise_bad_request_for_known_db_error(exc)
        raise
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(row)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int) -> Response:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM core.users WHERE user_id = %s;", (user_id,))
                deleted = cur.rowcount
                conn.commit()
    except psycopg.Error as exc:
        raise_bad_request_for_known_db_error(exc)
        raise
    if deleted == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
