"""A minimal endpoint the frontend calls to prove it can reach the API."""

from fastapi import APIRouter

from app.schemas.health import HelloResponse

router = APIRouter(tags=["hello"])


@router.get("/hello", response_model=HelloResponse)
def hello() -> HelloResponse:
    return HelloResponse(message="Hello from the KaushalSetu API")
