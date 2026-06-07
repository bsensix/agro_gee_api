from fastapi import APIRouter

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}
