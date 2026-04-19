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

## 14) Complete backend directory and file map (all project files)

This is the full backend map, grouped by folder, with one-line purpose per file.

### backend root files

- [backend/pyproject.toml](backend/pyproject.toml): backend package metadata, dependency groups, pytest settings.
- [backend/.env](backend/.env): local runtime config (not for committing secrets).
- [backend/.env.example](backend/.env.example): environment template for setup.
- [backend/.DS_Store](backend/.DS_Store): macOS metadata artifact.

### backend/app

- [backend/app/__init__.py](backend/app/__init__.py): package marker.
- [backend/app/main.py](backend/app/main.py): FastAPI app creation, CORS, router mounting.
- [backend/app/.DS_Store](backend/app/.DS_Store): macOS metadata artifact.

### backend/app/api

- [backend/app/api/__init__.py](backend/app/api/__init__.py): package marker.
- [backend/app/api/deps.py](backend/app/api/deps.py): cached service wiring + auth dependencies.
- [backend/app/api/routes_chat.py](backend/app/api/routes_chat.py): chat routes, session CRUD routes, websocket stream route.
- [backend/app/api/routes_health.py](backend/app/api/routes_health.py): health and index status route.

### backend/app/core

- [backend/app/core/__init__.py](backend/app/core/__init__.py): package marker.
- [backend/app/core/config.py](backend/app/core/config.py): strongly-typed settings from env.
- [backend/app/core/errors.py](backend/app/core/errors.py): shared error types and service_unavailable helper.

### backend/app/models

- [backend/app/models/__init__.py](backend/app/models/__init__.py): package marker.
- [backend/app/models/chat.py](backend/app/models/chat.py): API contracts for chat, stream, sessions, stored messages.
- [backend/app/models/corpus.py](backend/app/models/corpus.py): verse/chunk corpus models used in ingestion and retrieval.

### backend/app/rag

- [backend/app/rag/__init__.py](backend/app/rag/__init__.py): package marker.
- [backend/app/rag/chunker.py](backend/app/rag/chunker.py): splits verses/purports into retrieval-friendly chunks.
- [backend/app/rag/citations.py](backend/app/rag/citations.py): backend-owned citation list builder and deduper.
- [backend/app/rag/corpus_report.py](backend/app/rag/corpus_report.py): corpus stats and quality gates.
- [backend/app/rag/embeddings.py](backend/app/rag/embeddings.py): embedding provider abstraction and factory.
- [backend/app/rag/generator.py](backend/app/rag/generator.py): generation engine, provider adapters, contract enforcement, post-processing.
- [backend/app/rag/intent_router.py](backend/app/rag/intent_router.py): intent classification logic.
- [backend/app/rag/normalizer.py](backend/app/rag/normalizer.py): text cleanup helpers.
- [backend/app/rag/parser.py](backend/app/rag/parser.py): parses extracted PDF text into verse records.
- [backend/app/rag/pdf_loader.py](backend/app/rag/pdf_loader.py): PDF text extraction via PyMuPDF.
- [backend/app/rag/prompt.py](backend/app/rag/prompt.py): system/user prompt construction.
- [backend/app/rag/retriever.py](backend/app/rag/retriever.py): query embedding, search, rerank, diversity selection.
- [backend/app/rag/theme_router.py](backend/app/rag/theme_router.py): theme mapping and seed-verse helpers.
- [backend/app/rag/vector_store.py](backend/app/rag/vector_store.py): index build/load/search.

### backend/app/services

- [backend/app/services/__init__.py](backend/app/services/__init__.py): package marker.
- [backend/app/services/auth_service.py](backend/app/services/auth_service.py): Supabase token -> user resolution.
- [backend/app/services/chat_repository.py](backend/app/services/chat_repository.py): PostgreSQL persistence for users/sessions/messages.
- [backend/app/services/chat_service.py](backend/app/services/chat_service.py): central business orchestrator.
- [backend/app/services/session_memory.py](backend/app/services/session_memory.py): short-term in-memory verse repetition guard.

### backend/scripts

- [backend/scripts/ingest.py](backend/scripts/ingest.py): complete ingest/index build pipeline.
- [backend/scripts/inspect_corpus.py](backend/scripts/inspect_corpus.py): sample extraction output tool.

### backend/sql

- [backend/sql/chat_schema.sql](backend/sql/chat_schema.sql): SQL DDL for users, sessions, messages, indexes.

### backend/tests

- [backend/tests/test_chunker.py](backend/tests/test_chunker.py): chunking behavior tests.
- [backend/tests/test_citations.py](backend/tests/test_citations.py): citation dedupe tests.
- [backend/tests/test_corpus_report.py](backend/tests/test_corpus_report.py): corpus metrics and gate tests.
- [backend/tests/test_generator_formatting.py](backend/tests/test_generator_formatting.py): generator formatting contract tests.
- [backend/tests/test_intent_emotional_states.py](backend/tests/test_intent_emotional_states.py): intent and emotional-state routing tests.
- [backend/tests/test_normalizer.py](backend/tests/test_normalizer.py): text normalization tests.
- [backend/tests/test_parser.py](backend/tests/test_parser.py): verse/parser extraction tests.

### backend/data

#### fixtures/local
- [backend/data/fixtures/local/.gitkeep](backend/data/fixtures/local/.gitkeep): keeps folder in git.
- [backend/data/fixtures/local/extraction-sample.txt](backend/data/fixtures/local/extraction-sample.txt): sample extraction artifact.

#### index
- [backend/data/index/.gitkeep](backend/data/index/.gitkeep): keeps folder in git.
- [backend/data/index/faiss.index](backend/data/index/faiss.index): vector index binary.
- [backend/data/index/metadata.json](backend/data/index/metadata.json): chunk metadata and index config.

#### processed
- [backend/data/processed/.gitkeep](backend/data/processed/.gitkeep): keeps folder in git.
- [backend/data/processed/chunks.jsonl](backend/data/processed/chunks.jsonl): chunk corpus artifact.
- [backend/data/processed/corpus_report.json](backend/data/processed/corpus_report.json): quality/stats report.
- [backend/data/processed/verses.jsonl](backend/data/processed/verses.jsonl): parsed verses artifact.

#### raw
- [backend/data/raw/.gitkeep](backend/data/raw/.gitkeep): keeps folder in git.
- [backend/data/raw/Bhagavad-Gita As It Is.pdf](backend/data/raw/Bhagavad-Gita%20As%20It%20Is.pdf): source corpus PDF.

#### data root
- [backend/data/.DS_Store](backend/data/.DS_Store): macOS metadata artifact.

### backend/gitagpt_backend.egg-info

- [backend/gitagpt_backend.egg-info/PKG-INFO](backend/gitagpt_backend.egg-info/PKG-INFO): package metadata snapshot.
- [backend/gitagpt_backend.egg-info/SOURCES.txt](backend/gitagpt_backend.egg-info/SOURCES.txt): packaged file list.
- [backend/gitagpt_backend.egg-info/dependency_links.txt](backend/gitagpt_backend.egg-info/dependency_links.txt): packaging metadata.
- [backend/gitagpt_backend.egg-info/requires.txt](backend/gitagpt_backend.egg-info/requires.txt): dependency list snapshot.
- [backend/gitagpt_backend.egg-info/top_level.txt](backend/gitagpt_backend.egg-info/top_level.txt): top-level module names.

## 15) generator.py function walkthrough (teacher style)

Think of `generator.py` as a smart answer factory with 3 layers:

1. Provider adapters: how to talk to Modal/Groq/OpenAI.
2. Contract checker: verify output quality and structure.
3. Cleaner/repairer: polish wording into consistent output.

File: [backend/app/rag/generator.py](backend/app/rag/generator.py)

### Class methods (the pipeline engine)

- `Generator.__init__(settings)`
	- Stores runtime settings.

- `generate(question, chunks, intent, theme, avoid_verses, memory_context, on_token)`
	- Main entry point.
	- Chooses provider by `LLM_PROVIDER`.
	- `template` mode returns deterministic output directly.
	- Other providers produce raw text, then `_enforce_contract` validates/fixes.
	- If `on_token` callback exists, tokens are emitted progressively.

- `_generate_with_modal_fallback(...)`
	- First tries Modal.
	- If Modal fails, tries Groq fallback (if key exists).
	- If both fail, raises combined runtime failure.

- `_modal(...)`
	- Validates Modal key and delegates to `_chat_completions_request`.

- `_groq(...)`
	- Validates Groq key and delegates to `_chat_completions_request`.

- `_chat_completions_request(...)`
	- Shared HTTP adapter for OpenAI-compatible endpoints.
	- Builds prompt from chunks + memory context.
	- Sends to `/chat/completions`.
	- Extracts assistant content from JSON payload.
	- Supports token callback streaming.

- `_openai(...)`
	- Uses AsyncOpenAI SDK directly.
	- Supports both streaming and non-streaming response paths.

### Core fallback and validation functions

- `_template_answer(...)`
	- Deterministic fallback generator.
	- Uses theme profile + stable seed + selected verse.
	- Produces sectioned response shape.

- `_enforce_contract(...)`
	- Most critical guardrail.
	- Ensures section order, tone, practical quality, and theme-mechanism fit.
	- Falls back to `_template_answer` if output is weak or malformed.

- `_extract_sections(...)`
	- Splits generated answer into named sections for validation logic.

- `_is_theme_mechanism_valid(...)`
	- Theme-specific correctness check for causal explanation.

- `_is_theme_action_valid(...)`
	- Theme-specific check for practical reflection quality.

- `_has_real_life_context(...)`
	- Checks whether answer includes practical real-life context.

### Prompt and context-shaping helpers

- `_infer_real_life_context(...)`
	- Converts user question into realistic context phrases.

- `_contextualize_step(...)`
	- Adjusts practical action bullet to match inferred context.

- `_pick_verse(...)`
	- Chooses verse anchor from retrieved chunks with fallback default.

- `_stable_index(...)` and `_pick_variant(...)`
	- Ensure deterministic style variation (same input, stable output pattern).

- `_theme_profile(...)`
	- Returns theme-specific templates and wording building blocks.

- `_is_real_life_query(...)` and `_peace_subtheme(...)`
	- Detect mode and subtheme, especially for nuanced peace/comparison cases.

### Output cleanup and polish helpers

- `_post_process_answer(...)`
	- Final cleanup pipeline that calls multiple normalizers.

- `_normalize_section_headings(...)`
	- Makes heading format consistent.

- `_normalize_practical_steps(...)`
	- Cleans and standardizes practical bullet lines.

- `_normalize_bullets(...)`
	- Bullet punctuation/shape cleanup.

- `_strip_anchor_lines(...)`
	- Removes internal anchor artifacts.

- `_normalize_repetitive_context_phrase(...)`
	- Reduces repeated context phrasing.

- `_normalize_wisdom_section(...)`
	- Repairs section wording if wisdom section is weak/awkward.

- `_replace_generic_wellness_language(...)`
	- Replaces generic therapy-like wording with Gita-grounded language.

- `_correct_guna_state_mislabels(...)`
	- Repairs mislabeled guna/state framing patterns.

- `_normalize_closing_line(...)`, `_clean_punchline(...)`, `_generate_new_punchline(...)`
	- Ensures closing line is concise, grounded, and non-repetitive.

- `_stream_tokens(...)`
	- Splits text into token-like chunks for simulated word streaming.


