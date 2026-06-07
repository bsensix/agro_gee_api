from dataclasses import dataclass
from typing import Annotated, Mapping

from fastapi import Header, HTTPException

from agro_gee_api.db import get_connection


@dataclass(frozen=True)
class AuthzContext:
    requester_user_id: int
    allowed_user_ids: tuple[int, ...]
    requester_role: str | None = None


def has_admin_or_internal_scope(authz: AuthzContext) -> bool:
    role = (authz.requester_role or "").strip().lower()
    return role in {"admin", "internal"}


def _read_row_value(row: object, *, key: str, index: int) -> object | None:
    if isinstance(row, Mapping):
        return row.get(key)

    if isinstance(row, tuple):
        if 0 <= index < len(row):
            return row[index]
        return None

    return getattr(row, key, None)


def _parse_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise ValueError("Unsupported user id type")


def get_authz_context(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> AuthzContext:
    if x_user_id is None:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")

    try:
        requester_user_id = int(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header") from exc

    if requester_user_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH RECURSIVE allowed_users AS (
                    SELECT user_id
                    FROM core.users
                    WHERE user_id = %s
                    UNION ALL
                    SELECT u.user_id
                    FROM core.users AS u
                    JOIN allowed_users AS au
                      ON u.parent_user_id = au.user_id
                )
                SELECT user_id
                FROM allowed_users
                ORDER BY user_id;
                """,
                (requester_user_id,),
            )
            rows = cur.fetchall()

            cur.execute(
                """
                SELECT role
                FROM core.users
                WHERE user_id = %s;
                """,
                (requester_user_id,),
            )
            requester_row = cur.fetchone()

    if not rows:
        raise HTTPException(status_code=400, detail="X-User-Id does not exist")

    if requester_row is None:
        raise HTTPException(status_code=400, detail="X-User-Id does not exist")

    try:
        allowed_user_ids = tuple(
            _parse_int(_read_row_value(row, key="user_id", index=0)) for row in rows
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=500, detail="Authorization data malformed"
        ) from exc

    role_value = _read_row_value(requester_row, key="role", index=0)
    requester_role = (
        None if role_value is None else str(role_value).strip().lower() or None
    )

    return AuthzContext(
        requester_user_id=requester_user_id,
        allowed_user_ids=allowed_user_ids,
        requester_role=requester_role,
    )
