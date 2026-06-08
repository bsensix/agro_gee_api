from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException


@dataclass(frozen=True)
class AuthzContext:
    requester_user_id: int
    allowed_user_ids: tuple[int, ...]
    requester_role: str | None = None


def has_admin_or_internal_scope(authz: AuthzContext) -> bool:
    role = (authz.requester_role or "").strip().lower()
    return role in {"admin", "internal"}


def get_authz_context(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_requester_role: Annotated[str | None, Header(alias="X-Requester-Role")] = None,
) -> AuthzContext:
    _ = x_requester_role
    if x_user_id is None:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")

    try:
        requester_user_id = int(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header") from exc

    if requester_user_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header")

    return AuthzContext(
        requester_user_id=requester_user_id,
        allowed_user_ids=(requester_user_id,),
        requester_role=None,
    )
