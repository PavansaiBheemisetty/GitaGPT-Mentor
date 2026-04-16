import uuid

import httpx

from app.core.config import Settings
from app.core.errors import GitaGPTError
from app.models.chat import ChatRequest, ChatResponse, ProviderInfo
from app.rag.citations import backend_citations
from app.rag.embeddings import create_embedding_provider
from app.rag.generator import Generator
from app.rag.intent_router import classify_query_intent, map_intent_to_theme
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore
from app.services.session_memory import ConversationVerseMemory


class ChatService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.embeddings = create_embedding_provider(settings)
        self.store = VectorStore(settings.faiss_index_path, settings.faiss_metadata_path)
        self.store.load()
        self.retriever = Retriever(settings, self.embeddings, self.store)
        self.generator = Generator(settings)
        self.verse_memory = ConversationVerseMemory(window_size=28)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        request_id = str(uuid.uuid4())
        self._validate_request(request)
        intent_route = classify_query_intent(request.message, embeddings=self.embeddings)

        provider = ProviderInfo(
            embedding=self.embeddings.model_name,
            llm=f"{self.settings.llm_provider}:{self._llm_model_name()}",
        )

        if intent_route.intent == "out_of_scope":
            return ChatResponse(
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

        theme = map_intent_to_theme(intent_route.intent)
        recent_verses = self.verse_memory.recent_verses(request.conversation_id)
        chunks = self.retriever.retrieve(
            request.message,
            top_k=request.top_k,
            theme=theme,
            avoid_verses=recent_verses,
        )
        if not chunks:
            return ChatResponse(
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
        try:
            answer = await self.generator.generate(
                request.message,
                chunks,
                intent=intent_route.intent,
                theme=theme,
                avoid_verses=[f"{chapter}.{verse}" for chapter, verse in sorted(recent_verses)],
            )
        except (httpx.HTTPError, RuntimeError) as exc:
            raise GitaGPTError(
                "The language model provider is unavailable.",
                cause=str(exc),
                fix="Start Ollama, switch LLM_PROVIDER, or configure OPENAI_API_KEY.",
            ) from exc
        citations = backend_citations(chunks)
        warnings = []
        confidence = "sufficient" if citations else "error"
        if not citations:
            warnings.append("trust_failure_no_valid_citations")
        self.verse_memory.remember(request.conversation_id, chunks)
        return ChatResponse(
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

    def _validate_request(self, request: ChatRequest) -> None:
        if len(request.message) > self.settings.max_message_chars:
            raise ValueError(f"message exceeds {self.settings.max_message_chars} characters")
        if len(request.history) > self.settings.max_history_turns:
            raise ValueError(f"history exceeds {self.settings.max_history_turns} turns")
        history_chars = sum(len(item.content) for item in request.history)
        if history_chars > self.settings.max_history_chars:
            raise ValueError(f"history exceeds {self.settings.max_history_chars} characters")

    def _llm_model_name(self) -> str:
        if self.settings.llm_provider == "ollama":
            return self.settings.ollama_model
        if self.settings.llm_provider == "openai":
            return self.settings.openai_model
        return "template"
