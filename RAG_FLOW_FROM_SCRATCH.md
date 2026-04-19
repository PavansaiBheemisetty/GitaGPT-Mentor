# GitaGPT Backend RAG Flow From Scratch

This is a detailed backend teaching note for this repository.

If you remember only one line:

POST /chat does: validate -> classify -> retrieve -> generate -> validate output -> cite -> persist -> return.

## 1) What RAG means here

RAG is Retrieval Augmented Generation.

- Retrieval: find relevant Bhagavad Gita translation or purport chunks.
- Generation: produce an answer using that context and current intent/theme.

In this backend, RAG is not just search + answer. It also has:

- intent routing
- theme-aware reranking
- strict response contract checks
- backend-owned citations
- optional authenticated session persistence
- websocket token streaming

## 2) End-to-end request flow for POST /chat

Main route: [backend/app/api/routes_chat.py](backend/app/api/routes_chat.py)
Main orchestrator: [backend/app/services/chat_service.py](backend/app/services/chat_service.py)

### Flow in order

1. FastAPI receives request at /chat.
2. Route resolves optional user via Bearer token dependency in [backend/app/api/deps.py](backend/app/api/deps.py).
3. Route gets cached ChatService instance from deps.
4. Route calls await ChatService.chat(request, user=user).
5. ChatService validates message and history limits.
6. ChatService resolves memory context:
- request history
- optional DB history/summary if user + repository are enabled
7. ChatService classifies intent using classify_query_intent.
8. If out_of_scope: returns safe fallback and persists turn if possible.
9. ChatService maps intent to theme.
10. ChatService gets recent verses from in-memory conversation memory.
11. Retriever retrieves and reranks chunks from vector store.
12. If no chunks survive threshold: returns insufficient context fallback and persists turn.
13. Generator generates answer with selected provider:
- modal (primary) with groq fallback
- groq
- openai
- template
14. Generator enforces response contract; can fallback to deterministic template.
15. ChatService builds citations from retrieved chunks.
16. ChatService updates recent-verse memory.
17. ChatService persists user and assistant turns (if DB enabled and user authenticated).
18. ChatService returns ChatResponse.
19. Route converts known failures to HTTP 422/503 with actionable fix details.

## 2.1 Full chat API surface (newer routes included)

All defined in [backend/app/api/routes_chat.py](backend/app/api/routes_chat.py):

- POST /chat
- GET /chat/sessions
- POST /chat/sessions
- PATCH /chat/sessions/{session_id} (rename)
- DELETE /chat/sessions/{session_id}
- DELETE /sessions/{session_id} (alias route for compatibility)
- GET /chat/sessions/{session_id}/messages
- WS /chat/stream/ws

Auth requirements:

- /chat accepts optional auth (Depends(get_optional_user))
- session CRUD/message routes require auth (Depends(get_current_user))
- stream route checks token directly and enforces AUTH_REQUIRED when enabled

## 3) Streaming flow for WS /chat/stream/ws

Route: [backend/app/api/routes_chat.py](backend/app/api/routes_chat.py)

### Streaming lifecycle

1. Frontend opens websocket at /chat/stream/ws.
2. Backend accepts socket.
3. Client sends message payload (message, conversation_id, top_k, access_token).
4. Backend resolves user from access_token via SupabaseAuthService.
5. If AUTH_REQUIRED=true and no user: send error event and close socket.
6. Backend sends thinking event.
7. Backend calls ChatService.chat with on_token callback.
8. Callback emits token events progressively.
9. On completion backend sends done event with full ChatResponse.
10. On failure backend sends error event.

## 4) Major backend folders and what each does

### [backend/app](backend/app)

Runtime API and RAG system.

### [backend/app/api](backend/app/api)

HTTP + WebSocket endpoints and request dependencies.

- routes_chat.py: chat endpoint, session endpoints, streaming endpoint
- routes_health.py: health and index status
- deps.py: cached services and auth dependencies

Newer dependency details in [backend/app/api/deps.py](backend/app/api/deps.py):

- get_chat_service()
- get_chat_repository()
- get_auth_service()
- get_optional_user()
- get_current_user()
- clear_service_cache()

### [backend/app/core](backend/app/core)

Configuration and shared error helpers.

- config.py: Settings model from env
- errors.py: GitaGPTError and service_unavailable helper

### [backend/app/models](backend/app/models)

Pydantic schemas for input/output.

- chat.py: request/response/session models
- corpus.py: verse/chunk corpus models

Newer chat model additions in [backend/app/models/chat.py](backend/app/models/chat.py):

- ChatStreamRequest
- SessionCreateRequest
- SessionRenameRequest
- SessionSummary
- StoredMessage

### [backend/app/rag](backend/app/rag)

All RAG mechanics.

- intent_router.py
- theme_router.py
- retriever.py
- generator.py
- prompt.py
- vector_store.py
- embeddings.py
- chunker.py
- parser.py
- pdf_loader.py
- normalizer.py
- citations.py
- corpus_report.py

### [backend/app/services](backend/app/services)

Service-level orchestration and persistence/auth integration.

- chat_service.py: main orchestrator
- chat_repository.py: PostgreSQL session/message persistence
- auth_service.py: Supabase user resolution
- session_memory.py: recent verse memory

Repository schema SQL file:

- [backend/sql/chat_schema.sql](backend/sql/chat_schema.sql): explicit SQL migration for users/chat_sessions/messages and indexes

### [backend/scripts](backend/scripts)

Tooling scripts.

- ingest.py: build verses/chunks/index
- inspect_corpus.py: extraction inspection helper

### [backend/data](backend/data)

Corpus and index files.

- raw: source PDF
- processed: verses/chunks/report
- index: faiss + metadata
- fixtures/local: local extraction samples

### [backend/tests](backend/tests)

Unit tests for parser, normalizer, chunker, citations, routing checks.

## 5) Deep dive: ChatService

File: [backend/app/services/chat_service.py](backend/app/services/chat_service.py)

### __init__

Initializes:

- embedding provider
- vector store and load()
- retriever
- generator
- conversation verse memory
- optional repository for persistence

### chat(...)

This is the business pipeline.

Important behaviors:

- out_of_scope early return
- insufficient_context early return
- memory_context generation from recent turns
- provider metadata attached in response
- citations always generated backend-side from retrieved chunks
- persistence is attempted for user conversations

### _resolve_history_and_summary

If authenticated and repository enabled:

- loads DB recent history
- loads session summary

Else uses request history only.

### _build_memory_context

Builds compact prompt context from latest turns and optional summary.

### _persist_turn

Writes user and assistant messages to DB and refreshes summary.

If repository not configured while persistence is required, raises service_unavailable.

## 6) Deep dive: Retriever

File: [backend/app/rag/retriever.py](backend/app/rag/retriever.py)

### retrieve(...)

1. Embed query
2. Oversample from vector store
3. Rerank by theme and type and recency
4. Select diverse verse/type set
5. Filter below retrieval_min_score
6. Return RetrievedChunk list

### _rerank(...)

Score shaping:

- theme seed bonus via theme_router
- translation/purport preference
- recent-verse penalty

### _select_diverse(...)

Avoids over-concentration on one verse and tries balanced selection.

## 7) Deep dive: Generator

File: [backend/app/rag/generator.py](backend/app/rag/generator.py)

Generator handles text production and output quality enforcement.

### generate(...)

Dispatch by llm_provider:

- template
- modal
- groq
- openai

After provider response, it runs _enforce_contract() and optionally streams final tokens via on_token callback.

### _generate_with_modal_fallback(...)

- tries Modal first
- if Modal fails, tries Groq (if configured)
- raises combined runtime error when both fail

### _modal(...), _groq(...), _openai(...)

Provider-specific integrations.

- Modal/Groq use OpenAI-compatible chat-completions request path
- OpenAI uses AsyncOpenAI SDK

### _template_answer(...)

Deterministic fallback with theme profiles.

- sectioned output
- stable variant selection
- real-life context inference
- bullet normalization

### _enforce_contract(...)

Critical quality gate.

Checks structure and semantics before accepting output:

- required section order
- length range
- mechanism quality for theme
- practical action quality
- context quality

If failed, fallback template answer is returned.

## 8) Auth and persistence internals

### SupabaseAuthService

File: [backend/app/services/auth_service.py](backend/app/services/auth_service.py)

- resolves user via Supabase /auth/v1/user endpoint
- enabled only when Supabase URL + key exist

### ChatRepository

File: [backend/app/services/chat_repository.py](backend/app/services/chat_repository.py)

- asyncpg pooled connection
- lazy schema bootstrap
- user/session/message CRUD
- session summaries refreshed from recent turns
- session title auto-derivation from first message
- legacy response_payload parsing + safe downgrade when payload shape is invalid

Important methods now commonly used by routes/services:

- ensure_user
- create_session
- ensure_session
- list_sessions
- list_messages
- rename_session
- delete_session
- append_message
- refresh_summary
- load_recent_history
- session_summary

## 9) Data contracts you should know

File: [backend/app/models/chat.py](backend/app/models/chat.py)

- ChatRequest
- ChatResponse
- ChatStreamRequest
- SessionSummary
- StoredMessage

These models define the backend/frontend contract and should be treated as stable unless intentionally changed.

Route response shapes to remember:

- rename returns: {"status": "success", "title": "..."}
- delete returns: {"status": "success"}
- websocket events: thinking, token, done, error

## 10) Config and environment overview

File: [backend/app/core/config.py](backend/app/core/config.py)

Important groups:

- runtime: APP_ENV, API_HOST, API_PORT, AUTH_REQUIRED
- auth/db: DATABASE_URL, SUPABASE_* keys
- corpus/index paths: PDF_PATH, PROCESSED_*, FAISS_*
- embeddings: EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_DEVICE
- llm: LLM_PROVIDER, MODAL_*, GROQ_*, OPENAI_*
- retrieval and limits: RETRIEVAL_*, MAX_HISTORY_*, MAX_MESSAGE_*
- streaming: STREAM_WORD_DELAY_MS

## 11) Common failure points and fixes

1. /chat gives 503 vector index missing
- fix: run [backend/scripts/ingest.py](backend/scripts/ingest.py)

2. /chat gives 422 message/history too large
- fix: shrink payload or adjust MAX_* settings

3. provider unavailable
- fix: configure MODAL_API_KEY and model; set GROQ fallback; or switch to template

4. sessions endpoints fail with persistence unavailable
- fix: set DATABASE_URL to reachable Postgres/Supabase pooler URL

5. auth failures on protected routes
- fix: valid Bearer token from Supabase client session

## 12) Ingestion pipeline recap

Script: [backend/scripts/ingest.py](backend/scripts/ingest.py)

Flow:

1. extract pages from PDF
2. parse verses
3. build and gate corpus report
4. chunk verses
5. embed chunks
6. build vector index and metadata

Without this, retrieval cannot operate.

## 13) Quick interview answer

What makes this backend robust?

- retrieval-first architecture
- intent/theme routing
- structured output contract enforcement
- backend-owned citation trust model
- graceful fallbacks for scope/context/provider issues
- optional auth + persistence + streaming support
