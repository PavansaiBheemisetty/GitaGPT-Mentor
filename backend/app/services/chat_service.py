import uuid
from typing import Awaitable, Callable, TYPE_CHECKING

import httpx

from app.core.config import Settings
from app.core.errors import GitaGPTError, service_unavailable
from app.models.chat import ChatMessage, ChatRequest, ChatResponse, ProviderInfo
from app.rag.citations import backend_citations
from app.rag.embeddings import create_embedding_provider
from app.rag.generator import Generator
from app.rag.intent_router import classify_query_intent, map_intent_to_theme
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore
from app.rag.prompt import SYSTEM_PROMPT
from app.services.session_memory import ConversationVerseMemory
from app.services.memory_builder import SessionMemoryBuilder

if TYPE_CHECKING:
    from app.services.chat_repository import AuthUser, ChatRepository


class ChatService:
    def __init__(self, settings: Settings, repository: "ChatRepository | None" = None) -> None:
        self.settings = settings
        self.repository = repository
        self.embeddings = create_embedding_provider(settings)
        self.store = VectorStore(settings.faiss_index_path, settings.faiss_metadata_path)
        self.store.load()
        self.retriever = Retriever(settings, self.embeddings, self.store)
        self.generator = Generator(settings)
        self.verse_memory = ConversationVerseMemory(window_size=28)
        self.memory_builder = SessionMemoryBuilder(
            max_chars=settings.session_memory_max_chars,
            summary_max_chars=settings.session_memory_summary_chars,
            recent_message_count=settings.session_memory_recent_messages,
        )

    async def chat(
        self,
        request: ChatRequest,
        *,
        user: "AuthUser | None" = None,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> ChatResponse:
        request_id = str(uuid.uuid4())
        self._validate_request(request)
        history = await self._resolve_history(request, user=user)
        intent_route = classify_query_intent(request.message, embeddings=self.embeddings)

        if intent_route.intent == "out_of_scope":
            provider = self._provider_info()
            response = ChatResponse(
                request_id=request_id,
                answer=(
                    "I can help with life guidance based on the Bhagavad Gita, "
                    "but this question seems outside that scope."
                ),
                intent="out_of_scope",
                theme=None,
                citations=[],
                retrieved_chunks=[],
                confidence="insufficient",
                warnings=["out_of_scope_query"],
                provider=provider,
            )
            if on_token:
                await on_token(response.answer)
            await self._persist_turn(user=user, request=request, response=response)
            return response

        theme = map_intent_to_theme(intent_route.intent)
        recent_verses = self.verse_memory.recent_verses(request.conversation_id)
        chunks = self.retriever.retrieve(
            request.message,
            top_k=request.top_k,
            theme=theme,
            avoid_verses=recent_verses,
        )
        if not chunks:
            provider = self._provider_info()
            response = ChatResponse(
                request_id=request_id,
                answer=(
                    "I do not have enough retrieved Gita context to answer that safely. "
                    "Try asking about a specific life situation such as stress, anger, setbacks, focus, or meaning."
                ),
                intent=intent_route.intent,
                theme=theme,
                citations=[],
                retrieved_chunks=[],
                confidence="insufficient",
                warnings=["insufficient_context"],
                provider=provider,
            )
            if on_token:
                await on_token(response.answer)
            await self._persist_turn(user=user, request=request, response=response)
            return response
        try:
            memory_result = self.memory_builder.build(
                system_prompt=SYSTEM_PROMPT,
                history=history,
                current_prompt="",
            )
            history_messages = memory_result.messages
            generation = await self.generator.generate(
                request.message,
                chunks,
                intent=intent_route.intent,
                theme=theme,
                avoid_verses=[f"{chapter}.{verse}" for chapter, verse in sorted(recent_verses)],
                history_messages=history_messages,
                on_token=on_token,
            )
        except (httpx.HTTPError, RuntimeError) as exc:
            raise GitaGPTError(
                "The language model provider is unavailable.",
                cause=str(exc),
                fix=(
                    "Set GROQ_API_KEY and GROQ_MODEL (primary). "
                    "Configure OPENROUTER_API_KEY for the built-in fallback chain. "
                    "Configure MODAL_API_KEY and MODAL_MODEL as last fallback."
                ),
            ) from exc
        citations = backend_citations(chunks)
        warnings = []
        confidence = "sufficient" if citations else "error"
        if not citations:
            warnings.append("trust_failure_no_valid_citations")
        self.verse_memory.remember(request.conversation_id, chunks)
        provider = self._provider_info(
            llm_provider=generation.provider,
            llm_model=generation.model,
            llm_attempts=generation.attempts,
        )
        response = ChatResponse(
            request_id=request_id,
            answer=generation.answer,
            intent=intent_route.intent,
            theme=theme,
            citations=citations,
            retrieved_chunks=chunks,
            confidence=confidence,
            warnings=warnings,
            provider=provider,
        )
        await self._persist_turn(user=user, request=request, response=response)
        return response

    def _validate_request(self, request: ChatRequest) -> None:
        if len(request.message) > self.settings.max_message_chars:
            raise ValueError(f"message exceeds {self.settings.max_message_chars} characters")
        history_chars = sum(len(item.content) for item in request.history)
        if history_chars > self.settings.session_memory_max_chars * 4:
            raise ValueError("history exceeds allowed request payload size")

    def _configured_llm_model_name(self) -> str:
        if self.settings.llm_provider == "groq":
            return self.settings.groq_model
        if self.settings.llm_provider == "modal":
            return self.settings.modal_model
        if self.settings.llm_provider in {"openrouter", "open-router"}:
            return "fallback-chain"
        return "template"

    def _provider_info(
        self,
        *,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        llm_attempts: list[str] | None = None,
    ) -> ProviderInfo:
        resolved_provider = llm_provider or self.settings.llm_provider
        resolved_model = llm_model or self._configured_llm_model_name()
        return ProviderInfo(
            embedding=self.embeddings.model_name,
            llm=f"{resolved_provider}:{resolved_model}",
            llm_provider=resolved_provider,
            llm_model=resolved_model,
            llm_attempts=llm_attempts or [],
        )

    async def _resolve_history(
        self,
        request: ChatRequest,
        *,
        user: "AuthUser | None",
    ) -> list[ChatMessage]:
        history = request.history
        if not user or not request.conversation_id or not self.repository or not self.repository.enabled:
            return history
        try:
            db_history = await self.repository.load_full_history(
                user.id,
                request.conversation_id,
            )
            if db_history:
                history = db_history
        except Exception:
            return history
        return history

    async def _persist_turn(
        self,
        *,
        user: "AuthUser | None",
        request: ChatRequest,
        response: ChatResponse,
    ) -> None:
        if not user or not request.conversation_id:
            return
        if not self.repository or not self.repository.enabled:
            raise service_unavailable(
                "Chat persistence is not configured.",
                cause="DATABASE_URL missing",
                fix="Set DATABASE_URL to your Supabase/Neon Postgres connection string.",
            )
        try:
            await self.repository.ensure_session(user, request.conversation_id, request.message)
            await self.repository.append_message(
                user_id=user.id,
                session_id=request.conversation_id,
                role="user",
                content=request.message,
            )
            await self.repository.append_message(
                user_id=user.id,
                session_id=request.conversation_id,
                role="assistant",
                content=response.answer,
                request_id=response.request_id,
                response_payload=response.model_dump(),
            )
            await self.repository.refresh_summary(user.id, request.conversation_id)
        except Exception as exc:
            raise service_unavailable(
                "Chat persistence is unavailable.",
                cause=str(exc),
                fix="Use the Supabase shared pooler connection string or enable the IPv4 add-on for the direct database host.",
            ) from exc
