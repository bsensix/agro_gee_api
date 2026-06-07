from fastapi import APIRouter

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}
