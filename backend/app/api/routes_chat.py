from fastapi import APIRouter, HTTPException, status

from app.api.deps import get_chat_service
from app.core.errors import GitaGPTError, service_unavailable
from app.models.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        service: ChatService = get_chat_service()
        return await service.chat(request)
    except FileNotFoundError as exc:
        raise service_unavailable(
            "The vector index is missing.",
            cause=str(exc),
            fix="Run `python scripts/ingest.py` from the backend directory.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except GitaGPTError as exc:
        raise service_unavailable(exc.message, cause=exc.cause or "unknown", fix=exc.fix or "Retry later.") from exc
