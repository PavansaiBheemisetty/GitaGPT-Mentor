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
from app.services.session_memory import ConversationVerseMemory

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

    async def chat(
        self,
        request: ChatRequest,
        *,
        user: "AuthUser | None" = None,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> ChatResponse:
        request_id = str(uuid.uuid4())
        self._validate_request(request)
        history, session_summary = await self._resolve_history_and_summary(request, user=user)
        memory_context = self._build_memory_context(history, session_summary)
        intent_route = classify_query_intent(request.message, embeddings=self.embeddings)

        provider = ProviderInfo(
            embedding=self.embeddings.model_name,
            llm=f"{self.settings.llm_provider}:{self._llm_model_name()}",
        )

        if intent_route.intent == "out_of_scope":
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
            answer = await self.generator.generate(
                request.message,
                chunks,
                intent=intent_route.intent,
                theme=theme,
                avoid_verses=[f"{chapter}.{verse}" for chapter, verse in sorted(recent_verses)],
                memory_context=memory_context,
                on_token=on_token,
            )
        except (httpx.HTTPError, RuntimeError) as exc:
            raise GitaGPTError(
                "The language model provider is unavailable.",
                cause=str(exc),
                fix="Set MODAL_API_KEY and MODAL_MODEL. Configure GROQ_API_KEY and GROQ_MODEL for fallback.",
            ) from exc
        citations = backend_citations(chunks)
        warnings = []
        confidence = "sufficient" if citations else "error"
        if not citations:
            warnings.append("trust_failure_no_valid_citations")
        self.verse_memory.remember(request.conversation_id, chunks)
        response = ChatResponse(
            request_id=request_id,
            answer=answer,
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
        if len(request.history) > self.settings.max_history_turns:
            raise ValueError(f"history exceeds {self.settings.max_history_turns} turns")
        history_chars = sum(len(item.content) for item in request.history)
        if history_chars > self.settings.max_history_chars:
            raise ValueError(f"history exceeds {self.settings.max_history_chars} characters")

    def _llm_model_name(self) -> str:
        if self.settings.llm_provider == "modal":
            return self.settings.modal_model
        if self.settings.llm_provider == "groq":
            return self.settings.groq_model
        if self.settings.llm_provider == "openai":
            return self.settings.openai_model
        return "template"

    async def _resolve_history_and_summary(
        self,
        request: ChatRequest,
        *,
        user: "AuthUser | None",
    ) -> tuple[list[ChatMessage], str | None]:
        history = request.history[-self.settings.memory_context_window :]
        summary = None
        if not user or not request.conversation_id or not self.repository or not self.repository.enabled:
            return history, summary
        try:
            db_history = await self.repository.load_recent_history(
                user.id,
                request.conversation_id,
                limit=self.settings.memory_context_window,
            )
            if db_history:
                history = db_history
            summary = await self.repository.session_summary(user.id, request.conversation_id)
        except Exception:
            return history, summary
        return history, summary

    def _build_memory_context(self, history: list[ChatMessage], summary: str | None) -> str | None:
        context_lines: list[str] = []
        if history:
            context_lines.append("Recent turns:")
            recent_history = history[-2:]
            for item in recent_history:
                speaker = "User" if item.role == "user" else "Assistant"
                compact = " ".join(item.content.split())
                context_lines.append(f"- {speaker}: {compact[:220]}")
        if not context_lines:
            return None
        return "\n".join(context_lines)[:3000]

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
