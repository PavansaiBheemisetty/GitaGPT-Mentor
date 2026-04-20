import asyncio
import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from app.api.deps import (
    get_auth_service,
    get_chat_repository,
    get_chat_service,
    get_current_user,
    get_optional_user,
)
from app.core.errors import GitaGPTError, service_unavailable
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    SessionCreateRequest,
    SessionRenameRequest,
    SessionSummary,
    StoredMessage,
)
from app.services.auth_service import SupabaseAuthService
from app.services.chat_repository import AuthUser, ChatRepository
from app.services.chat_service import ChatService
from app.core.config import get_settings

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: AuthUser | None = Depends(get_optional_user),
) -> ChatResponse:
    try:
        service: ChatService = get_chat_service()
        return await service.chat(request, user=user)
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


@router.get("/chat/sessions", response_model=list[SessionSummary])
async def list_sessions(user: AuthUser = Depends(get_current_user)) -> list[SessionSummary]:
    repository = get_chat_repository()
    if not repository.enabled:
        raise service_unavailable(
            "Session persistence is not configured.",
            cause="DATABASE_URL missing",
            fix="Set DATABASE_URL in backend/.env.",
        )
    try:
        return await repository.list_sessions(user.id)
    except (OSError, asyncpg.PostgresError, RuntimeError, ValueError) as exc:
        raise service_unavailable(
            "Session persistence is unavailable.",
            cause=str(exc),
            fix="Use the Supabase shared pooler connection string or enable the IPv4 add-on for the direct database host.",
        ) from exc


@router.post("/chat/sessions", response_model=SessionSummary)
async def create_session(
    payload: SessionCreateRequest,
    user: AuthUser = Depends(get_current_user),
) -> SessionSummary:
    repository = get_chat_repository()
    if not repository.enabled:
        raise service_unavailable(
            "Session persistence is not configured.",
            cause="DATABASE_URL missing",
            fix="Set DATABASE_URL in backend/.env.",
        )
    try:
        return await repository.create_session(user, title=payload.title)
    except (OSError, asyncpg.PostgresError, RuntimeError, ValueError) as exc:
        raise service_unavailable(
            "Session persistence is unavailable.",
            cause=str(exc),
            fix="Use the Supabase shared pooler connection string or enable the IPv4 add-on for the direct database host.",
        ) from exc


@router.patch("/chat/sessions/{session_id}")
async def rename_session(
    session_id: str,
    payload: SessionRenameRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    repository = get_chat_repository()
    if not repository.enabled:
        raise service_unavailable(
            "Session persistence is not configured.",
            cause="DATABASE_URL missing",
            fix="Set DATABASE_URL in backend/.env.",
        )
    try:
        await repository.rename_session(user.id, session_id, payload.title)
        return {"status": "success", "title": payload.title}
    except ValueError as exc:
        if str(exc) == "session not found for this user":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (OSError, asyncpg.PostgresError, RuntimeError) as exc:
        raise service_unavailable("Session persistence is unavailable.", cause=str(exc)) from exc

@router.delete("/chat/sessions/{session_id}")
@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    repository = get_chat_repository()
    if not repository.enabled:
        raise service_unavailable(
            "Session persistence is not configured.",
            cause="DATABASE_URL missing",
            fix="Set DATABASE_URL in backend/.env.",
        )
    try:
        await repository.delete_session(user.id, session_id)
        return {"status": "success"}
    except ValueError as exc:
        if str(exc) == "session not found for this user":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (OSError, asyncpg.PostgresError, RuntimeError) as exc:
        raise service_unavailable("Session persistence is unavailable.", cause=str(exc)) from exc


@router.get("/chat/sessions/{session_id}/messages", response_model=list[StoredMessage])
async def list_session_messages(
    session_id: str,
    user: AuthUser = Depends(get_current_user),
) -> list[StoredMessage]:
    repository = get_chat_repository()
    if not repository.enabled:
        raise service_unavailable(
            "Session persistence is not configured.",
            cause="DATABASE_URL missing",
            fix="Set DATABASE_URL in backend/.env.",
        )
    try:
        rows = await repository.list_messages(user.id, session_id)
        if not rows:
            return []
        return rows
    except (OSError, asyncpg.PostgresError, RuntimeError, ValueError) as exc:
        raise service_unavailable(
            "Session persistence is unavailable.",
            cause=str(exc),
            fix="Use the Supabase shared pooler connection string or enable the IPv4 add-on for the direct database host.",
        ) from exc


@router.websocket("/chat/stream/ws")
async def stream_chat(websocket: WebSocket) -> None:
    settings = get_settings()
    auth_service: SupabaseAuthService = get_auth_service()
    repository: ChatRepository = get_chat_repository()
    chat_service: ChatService = get_chat_service()
    await websocket.accept()

    try:
        while True:
            payload = await websocket.receive_json()
            stream_request = ChatStreamRequest(**payload)
            access_token = str(payload.get("access_token", "") or "")
            user = await auth_service.resolve_user(access_token)
            if settings.auth_required and user is None:
                await websocket.send_json(
                    {"type": "error", "message": "Authentication required for streaming."}
                )
                await websocket.close(code=4401)
                return

            if user and stream_request.conversation_id and repository.enabled:
                try:
                    await repository.ensure_session(user, stream_request.conversation_id, stream_request.message)
                except (OSError, asyncpg.PostgresError, RuntimeError, ValueError) as exc:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "Session persistence is unavailable. Use the Supabase shared pooler connection string "
                                "or enable the IPv4 add-on for the direct database host."
                            ),
                        }
                    )
                    await websocket.close(code=1011)
                    return

            await websocket.send_json({"type": "thinking"})

            progressive = ""

            async def send_token(token: str) -> None:
                nonlocal progressive
                progressive += token
                await websocket.send_json(
                    {
                        "type": "token",
                        "token": token,
                        "content": progressive,
                    }
                )
                if settings.stream_word_delay_ms > 0:
                    await asyncio.sleep(settings.stream_word_delay_ms / 1000)

            response = await chat_service.chat(
                ChatRequest(
                    message=stream_request.message,
                    conversation_id=stream_request.conversation_id,
                    top_k=stream_request.top_k,
                    history=[],
                ),
                user=user,
                on_token=send_token,
            )

            await websocket.send_json({"type": "done", "response": response.model_dump()})
    except WebSocketDisconnect:
        return
    except GitaGPTError as exc:
        logger.warning(
            "WebSocket chat provider failure: message=%s cause=%s",
            exc.message,
            exc.cause or "unknown",
        )
        detail_parts = [exc.message]
        if exc.cause:
            detail_parts.append(f"Cause: {exc.cause}")
        if exc.fix:
            detail_parts.append(f"Fix: {exc.fix}")
        await websocket.send_json({"type": "error", "message": " ".join(detail_parts)})
        await websocket.close(code=1011)
    except Exception as exc:
        logger.exception("Unexpected WebSocket chat streaming error.")
        await websocket.send_json(
            {
                "type": "error",
                "message": "Streaming failed unexpectedly. Please retry.",
            }
        )
        await websocket.close(code=1011)
