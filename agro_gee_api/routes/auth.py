from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}
