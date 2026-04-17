# GitaGPT Backend and RAG Flow: From Scratch (Teacher Style)

This guide explains the backend like you are in 12th grade and learning from a Python teacher who wants you to truly understand, not just memorize.

If you remember one line, remember this:

**`/chat` takes your question -> finds relevant Gita chunks -> builds a safe answer -> returns answer with citations.**

---

## 1) First, what is RAG in simple words?

RAG = Retrieval Augmented Generation.

Think of it like an open-book exam:

1. Retrieval: first find the right pages from the book.
2. Generation: then write the answer using only those pages.

Why do this?
- Without retrieval, model may guess.
- With retrieval, answers are grounded in actual source text.

In this project, the source is Bhagavad Gita text and purports processed into searchable chunks.

---

## 2) High-level backend map

Backend root is [backend](backend).

Main job split:
- [backend/app](backend/app): actual API + RAG logic used at runtime.
- [backend/scripts](backend/scripts): preprocessing and utilities.
- [backend/data](backend/data): raw PDF, processed files, index files.
- [backend/tests](backend/tests): unit tests.
- [backend/pyproject.toml](backend/pyproject.toml): Python package/dependency config.

---

## 3) What exactly happens when user sends POST /chat?

Route is in [backend/app/api/routes_chat.py](backend/app/api/routes_chat.py).

### Step-by-step call chain

1. FastAPI app receives request at `/chat`.
2. Function `chat(request: ChatRequest)` runs in [backend/app/api/routes_chat.py](backend/app/api/routes_chat.py).
3. It gets a singleton `ChatService` from `get_chat_service()` in [backend/app/api/deps.py](backend/app/api/deps.py).
4. It calls `await service.chat(request)` in [backend/app/services/chat_service.py](backend/app/services/chat_service.py).
5. Inside `ChatService.chat(...)`:
- Validate request size and history limits.
- Classify intent with `classify_query_intent(...)` from [backend/app/rag/intent_router.py](backend/app/rag/intent_router.py).
- If query is out of scope, return safe response early.
- Map intent to theme using `map_intent_to_theme(...)`.
- Get recent cited verses from conversation memory in [backend/app/services/session_memory.py](backend/app/services/session_memory.py).
- Retrieve chunks using `Retriever.retrieve(...)` in [backend/app/rag/retriever.py](backend/app/rag/retriever.py).
- If no chunks pass threshold, return "insufficient context" response.
- Generate answer using `Generator.generate(...)` in [backend/app/rag/generator.py](backend/app/rag/generator.py).
- Build citations using `backend_citations(...)` from [backend/app/rag/citations.py](backend/app/rag/citations.py).
- Store used verses in conversation memory to avoid repetition.
- Return `ChatResponse`.
6. Route-level exception handlers in [backend/app/api/routes_chat.py](backend/app/api/routes_chat.py) convert failures into proper HTTP errors.

### Short mental model

- Router = gatekeeper
- ChatService = orchestra conductor
- Retriever = library search engine
- Generator = answer writer + quality checker
- Citations = proof section

---

## 4) Core runtime files and how they connect

### App bootstrap

- [backend/app/main.py](backend/app/main.py)
  - `create_app()` creates FastAPI app.
  - Adds CORS middleware from settings.
  - Includes health and chat routers.

### API layer

- [backend/app/api/routes_chat.py](backend/app/api/routes_chat.py)
  - POST `/chat` endpoint.
  - Delegates all logic to `ChatService`.
  - Handles `FileNotFoundError`, `ValueError`, and custom `GitaGPTError`.

- [backend/app/api/routes_health.py](backend/app/api/routes_health.py)
  - GET `/health` endpoint.
  - Reports index existence and corpus report metadata.

- [backend/app/api/deps.py](backend/app/api/deps.py)
  - Provides cached `ChatService` via `@lru_cache`.
  - `clear_service_cache()` allows resetting singleton.

### Core config and errors

- [backend/app/core/config.py](backend/app/core/config.py)
  - Defines `Settings` using `pydantic-settings`.
  - Loads from `.env`.
  - Includes model provider, embedding provider, path and limits.

- [backend/app/core/errors.py](backend/app/core/errors.py)
  - `GitaGPTError`: custom backend error class.
  - `service_unavailable(...)`: helper to return structured HTTP 503.

### Data models

- [backend/app/models/chat.py](backend/app/models/chat.py)
  - `ChatRequest`, `ChatResponse`, `RetrievedChunk`, `Citation`, `ProviderInfo`, `ChatMessage`.

- [backend/app/models/corpus.py](backend/app/models/corpus.py)
  - `VerseRecord` and `ChunkRecord` for ingestion and indexing pipelines.

---

## 5) Deep explanation of main runtime flow classes

## 5.1 ChatService (main orchestrator)

File: [backend/app/services/chat_service.py](backend/app/services/chat_service.py)

### Constructor: `__init__(self, settings)`

Creates and wires:
- embedding provider (`create_embedding_provider`)
- vector store (`VectorStore(...)` and `load()`)
- retriever (`Retriever(...)`)
- generator (`Generator(...)`)
- session verse memory (`ConversationVerseMemory(window_size=28)`)

### `async chat(self, request)`

Main business logic:

1. Generate request id (UUID).
2. Validate request using `_validate_request`.
3. Detect intent with `classify_query_intent`.
4. Build provider metadata.
5. If `out_of_scope`: return safe and polite fallback.
6. Decide `theme` from intent.
7. Pull recent verses for current conversation id.
8. Retrieve chunks with reranking and diversity.
9. If no chunks: return insufficient-context response.
10. Generate answer from selected model provider.
11. Build citations from chunks.
12. Save verses to session memory.
13. Return final `ChatResponse`.

### `_validate_request(self, request)`

Guards against abuse and oversized input:
- `max_message_chars`
- `max_history_turns`
- `max_history_chars`

### `_llm_model_name(self)`

Returns configured model name based on provider (`ollama`, `openai`, or `template`).

---

## 5.2 Retriever (search + rerank + diversity)

File: [backend/app/rag/retriever.py](backend/app/rag/retriever.py)

### `retrieve(query, top_k=None, theme="general", avoid_verses=None)`

Pipeline:

1. Embed query (`embeddings.embed_texts`).
2. Search index with oversampling (`candidate_k = max(top_k*8, top_k+12)`).
3. Rerank with `_rerank(...)`.
4. Diversify with `_select_diverse(...)`.
5. Filter by score threshold (`retrieval_min_score`).
6. Return final `RetrievedChunk` list.

### `_rerank(...)`

Adjusts score:
- Theme seed verse match bonus.
- Type preference bonus (`translation` > `purport`).
- Recent verse penalty to avoid repetition.

### `_select_diverse(...)`

Prevents all results being from same verse:
- Group by `(chapter, verse)`.
- Prefer best translation and best purport for each verse.
- Fill leftovers from global ranked list if needed.

### `_chunk_is_recent(...)`

Checks exact verse or verse ranges against recent-memory set.

---

## 5.3 Generator (most important for your question)

File: [backend/app/rag/generator.py](backend/app/rag/generator.py)

This is where text answer is created and quality-controlled.

### Big idea

`Generator` has 3 provider paths:
- `template` (deterministic fallback mode)
- `ollama` (local LLM API)
- `openai` (OpenAI chat API)

Then it enforces output contract so response format remains safe and consistent.

### `async generate(question, chunks, intent, theme, avoid_verses)`

Decision logic:

1. Read provider from settings.
2. If `template`: directly return `_template_answer(...)`.
3. If `ollama`: call `_ollama(...)`, then `_enforce_contract(...)`.
4. If `openai`: call `_openai(...)`, then `_enforce_contract(...)`.
5. Unknown provider -> `ValueError`.

### `async _ollama(...)`

- Builds user prompt via `build_user_prompt(...)` in [backend/app/rag/prompt.py](backend/app/rag/prompt.py).
- Sends HTTP POST to `OLLAMA_BASE_URL/api/chat` with:
  - `SYSTEM_PROMPT`
  - user prompt
  - temperature, token and context settings
- Extracts text with `_extract_ollama_content(...)`.
- If output is empty because of `done_reason == "length"`, retries with compact prompt (`max_chunks=4`, smaller chunk chars).

### `async _openai(...)`

- Checks `OPENAI_API_KEY`.
- Imports `AsyncOpenAI`.
- Calls `chat.completions.create(...)` with system + user prompt.
- Returns model text.

### `_template_answer(...)`

Deterministic fallback answer engine.

It creates response sections in this exact format:
1. Direct Insight
2. Gita Wisdom
3. Why This Happens
4. Practical Reflection

How it builds those sections:
- Determines if query is real-life mode.
- Loads theme profile (`_theme_profile`) containing verse preferences, mechanism templates, action sets, punchlines.
- Picks verse from retrieved chunks (`_pick_verse`) else default verse.
- Creates deterministic seed (`_stable_index` using SHA256).
- Infers real-life context (`_infer_real_life_context`) from theme/question.
- Chooses section variants (`_pick_variant`) using seed.
- Contextualizes first bullet (`_contextualize_step`) for practical section.
- Runs final cleanup (`_post_process_answer`).

Because it uses stable seed, same question/theme produces stable style choices.

### `_enforce_contract(...)`

This is a safety+quality gate.

Checks:
- All 4 required headings present and in order.
- Word count within expected range.
- Real-life context presence when needed.
- Theme-mechanism validity via `_is_theme_mechanism_valid(...)`.
- Theme-action validity via `_is_theme_action_valid(...)`.
- Bullet count in practical section.

If checks fail, it falls back to `_template_answer(...)`.

So this is the anti-garbage filter.

### Other important helper functions in `generator.py`

- `_infer_real_life_context(...)`: picks practical context lines (deadline, breakup, conflict, etc.).
- `_extract_sections(...)`: slices output by heading boundaries for validation.
- `_is_theme_mechanism_valid(...)`: checks if explanation logic fits theme semantics.
- `_has_real_life_context(...)`: detects concrete real-world framing.
- `_post_process_answer(...)`: final cleanup pipeline.
- `_normalize_bullets(...)`: consistent bullet formatting.
- `_strip_anchor_lines(...)`: removes debugging artifacts.

In short: `generator.py` is not only a writer, it is also an editor + examiner.

---

## 5.4 Prompt builder

File: [backend/app/rag/prompt.py](backend/app/rag/prompt.py)

- `SYSTEM_PROMPT`: strict behavior policy and structure contract.
- `build_user_prompt(...)`: inserts question + retrieved chunks + intent/theme metadata.
- `_compact_chunk_text(...)`: truncates chunk text safely.
- `_is_real_life_intent(...)`: mode switch for emotional contexts.
- `_peace_subtheme_signal(...)`: distinguishes comparison vs restlessness.

---

## 5.5 Intent and theme routing

### Intent

File: [backend/app/rag/intent_router.py](backend/app/rag/intent_router.py)

- `classify_query_intent(query, embeddings=None)`:
  - keyword score + semantic score
  - out-of-scope check
  - returns `IntentRoute(intent, confidence, matched_keywords)`

- `map_intent_to_theme(intent)`:
  - current mapping is effectively identity mapping.

### Theme helper

File: [backend/app/rag/theme_router.py](backend/app/rag/theme_router.py)

- `classify_query_theme(...)`
- `theme_seed_verses(theme)` for retrieval boost.
- `theme_lens(theme)` for prompt metadata.
- `expand_verse_label(label)` for verse ranges.
- `chunk_matches_seed(...)` used by retriever reranking.

---

## 5.6 Vector and embeddings layer

### Embeddings

File: [backend/app/rag/embeddings.py](backend/app/rag/embeddings.py)

- `EmbeddingProvider` abstract base.
- `HashEmbeddingProvider`: local deterministic fallback.
- `SentenceTransformersProvider`: local transformer embeddings.
- `OpenAIEmbeddingProvider`: API embeddings.
- `create_embedding_provider(settings)`: provider factory.

### Vector store

File: [backend/app/rag/vector_store.py](backend/app/rag/vector_store.py)

- `build(vectors, chunks, metadata, provider)`:
  - builds FAISS index or JSON fallback index.
  - writes metadata sidecar with chunks.

- `load()`:
  - loads metadata and index.
  - raises if missing.

- `search(query_vector, top_k)`:
  - FAISS search or fallback dot-product search.

---

## 5.7 Citations and memory

### Citations

File: [backend/app/rag/citations.py](backend/app/rag/citations.py)

- `backend_citations(chunks)`:
  - dedupe by `(chapter, verse, type)`
  - include preview and score

### Conversation memory

File: [backend/app/services/session_memory.py](backend/app/services/session_memory.py)

- `recent_verses(conversation_id)` returns recently used refs.
- `remember(conversation_id, chunks)` stores refs (thread-safe).

Purpose: reduce verse repetition in ongoing conversation.

---

## 6) Ingestion flow (what must happen before /chat can work)

The retriever needs an index. That index is built by ingestion.

Main script: [backend/scripts/ingest.py](backend/scripts/ingest.py)

Flow:
1. Read settings.
2. Extract PDF pages via `extract_pdf_pages(...)` in [backend/app/rag/pdf_loader.py](backend/app/rag/pdf_loader.py).
3. Parse verse blocks via `parse_verses(...)` in [backend/app/rag/parser.py](backend/app/rag/parser.py).
4. Build corpus report via [backend/app/rag/corpus_report.py](backend/app/rag/corpus_report.py).
5. Enforce corpus quality gates.
6. Chunk verses via `chunk_verses(...)` in [backend/app/rag/chunker.py](backend/app/rag/chunker.py).
7. Write JSONL outputs.
8. Embed chunk texts.
9. Build vector index and metadata using `VectorStore.build(...)`.

If this is not done, `/chat` will fail with index-missing path.

---

## 7) Full backend directory + file-by-file explanation

Below is an explicit walkthrough of real project files under [backend](backend) (excluding virtual env internals).

## 7.1 Root-level backend files

- [backend/pyproject.toml](backend/pyproject.toml): package metadata, dependencies, optional extras, pytest config.
- [backend/.env.example](backend/.env.example): sample environment values.
- [backend/.env](backend/.env): local environment (runtime config).
- [backend/.DS_Store](backend/.DS_Store): macOS Finder metadata, not app logic.

## 7.2 App package files

### [backend/app](backend/app)

- [backend/app/__init__.py](backend/app/__init__.py): package marker.
- [backend/app/main.py](backend/app/main.py): FastAPI app factory and router wiring.
- [backend/app/.DS_Store](backend/app/.DS_Store): macOS metadata file.

### [backend/app/api](backend/app/api)

- [backend/app/api/__init__.py](backend/app/api/__init__.py): package marker.
- [backend/app/api/deps.py](backend/app/api/deps.py): cached dependency provider for `ChatService`.
- [backend/app/api/routes_chat.py](backend/app/api/routes_chat.py): POST `/chat` endpoint.
- [backend/app/api/routes_health.py](backend/app/api/routes_health.py): GET `/health` endpoint.

### [backend/app/core](backend/app/core)

- [backend/app/core/__init__.py](backend/app/core/__init__.py): package marker.
- [backend/app/core/config.py](backend/app/core/config.py): application settings.
- [backend/app/core/errors.py](backend/app/core/errors.py): custom errors and 503 helper.

### [backend/app/models](backend/app/models)

- [backend/app/models/__init__.py](backend/app/models/__init__.py): package marker.
- [backend/app/models/chat.py](backend/app/models/chat.py): chat request/response and citation schemas.
- [backend/app/models/corpus.py](backend/app/models/corpus.py): parsed verse/chunk schemas.

### [backend/app/rag](backend/app/rag)

- [backend/app/rag/__init__.py](backend/app/rag/__init__.py): package marker.
- [backend/app/rag/chunker.py](backend/app/rag/chunker.py): converts verses to chunk records.
- [backend/app/rag/citations.py](backend/app/rag/citations.py): deduplicates and builds citation payloads.
- [backend/app/rag/corpus_report.py](backend/app/rag/corpus_report.py): report stats and quality gates.
- [backend/app/rag/embeddings.py](backend/app/rag/embeddings.py): embedding providers + factory.
- [backend/app/rag/generator.py](backend/app/rag/generator.py): LLM/template generation + contract enforcement.
- [backend/app/rag/intent_router.py](backend/app/rag/intent_router.py): intent classifier and mapping helpers.
- [backend/app/rag/normalizer.py](backend/app/rag/normalizer.py): text cleanup and normalization utilities.
- [backend/app/rag/parser.py](backend/app/rag/parser.py): parses translation/purport by verse from extracted pages.
- [backend/app/rag/pdf_loader.py](backend/app/rag/pdf_loader.py): PDF extraction using PyMuPDF.
- [backend/app/rag/prompt.py](backend/app/rag/prompt.py): system and user prompt builder.
- [backend/app/rag/retriever.py](backend/app/rag/retriever.py): search + rerank + diversity + threshold.
- [backend/app/rag/theme_router.py](backend/app/rag/theme_router.py): theme semantics and seed verse helpers.
- [backend/app/rag/vector_store.py](backend/app/rag/vector_store.py): index build/load/search.

### [backend/app/services](backend/app/services)

- [backend/app/services/__init__.py](backend/app/services/__init__.py): package marker.
- [backend/app/services/chat_service.py](backend/app/services/chat_service.py): central orchestration service.
- [backend/app/services/session_memory.py](backend/app/services/session_memory.py): per-conversation verse memory.

## 7.3 Data files

### [backend/data](backend/data)

- [backend/data/.DS_Store](backend/data/.DS_Store): macOS metadata.

#### [backend/data/raw](backend/data/raw)
- [backend/data/raw/.gitkeep](backend/data/raw/.gitkeep): keep empty dir in git.
- [backend/data/raw/Bhagavad-Gita As It Is.pdf](backend/data/raw/Bhagavad-Gita%20As%20It%20Is.pdf): source corpus PDF.

#### [backend/data/processed](backend/data/processed)
- [backend/data/processed/.gitkeep](backend/data/processed/.gitkeep): keep dir in git.
- [backend/data/processed/verses.jsonl](backend/data/processed/verses.jsonl): parsed verse records.
- [backend/data/processed/chunks.jsonl](backend/data/processed/chunks.jsonl): chunked retrieval units.
- [backend/data/processed/corpus_report.json](backend/data/processed/corpus_report.json): ingestion quality report.

#### [backend/data/index](backend/data/index)
- [backend/data/index/.gitkeep](backend/data/index/.gitkeep): keep dir in git.
- [backend/data/index/faiss.index](backend/data/index/faiss.index): vector index file.
- [backend/data/index/metadata.json](backend/data/index/metadata.json): chunk metadata + build details.

#### [backend/data/fixtures/local](backend/data/fixtures/local)
- [backend/data/fixtures/local/.gitkeep](backend/data/fixtures/local/.gitkeep): keep dir in git.
- [backend/data/fixtures/local/extraction-sample.txt](backend/data/fixtures/local/extraction-sample.txt): sample extracted PDF pages.

## 7.4 Scripts

- [backend/scripts/ingest.py](backend/scripts/ingest.py): full corpus-to-index pipeline.
- [backend/scripts/inspect_corpus.py](backend/scripts/inspect_corpus.py): generate local extraction sample for inspection.

## 7.5 Tests

- [backend/tests/test_chunker.py](backend/tests/test_chunker.py): checks chunk metadata and purport splitting.
- [backend/tests/test_citations.py](backend/tests/test_citations.py): checks citation dedupe logic.
- [backend/tests/test_corpus_report.py](backend/tests/test_corpus_report.py): checks corpus counting and gate failures.
- [backend/tests/test_intent_emotional_states.py](backend/tests/test_intent_emotional_states.py): checks intent precedence and emotional-theme validation logic.
- [backend/tests/test_normalizer.py](backend/tests/test_normalizer.py): checks text normalization cleanup.
- [backend/tests/test_parser.py](backend/tests/test_parser.py): checks parser extraction of translation and purport.

## 7.6 Build metadata files

- [backend/gitagpt_backend.egg-info/PKG-INFO](backend/gitagpt_backend.egg-info/PKG-INFO): package metadata snapshot.
- [backend/gitagpt_backend.egg-info/SOURCES.txt](backend/gitagpt_backend.egg-info/SOURCES.txt): source file list for package.
- [backend/gitagpt_backend.egg-info/dependency_links.txt](backend/gitagpt_backend.egg-info/dependency_links.txt): dependency link metadata.
- [backend/gitagpt_backend.egg-info/requires.txt](backend/gitagpt_backend.egg-info/requires.txt): dependency list snapshot.
- [backend/gitagpt_backend.egg-info/top_level.txt](backend/gitagpt_backend.egg-info/top_level.txt): top-level package names.

## 7.7 Local cache artifacts (non-core logic)

- [backend/.pytest_cache/.gitignore](backend/.pytest_cache/.gitignore)
- [backend/.pytest_cache/CACHEDIR.TAG](backend/.pytest_cache/CACHEDIR.TAG)
- [backend/.pytest_cache/README.md](backend/.pytest_cache/README.md)
- [backend/.pytest_cache/v/cache/lastfailed](backend/.pytest_cache/v/cache/lastfailed)
- [backend/.pytest_cache/v/cache/nodeids](backend/.pytest_cache/v/cache/nodeids)

These are pytest runtime cache files, not production app code.

---

## 8) Important environment settings and what breaks when wrong

Defined by [backend/app/core/config.py](backend/app/core/config.py), values usually from [backend/.env](backend/.env) or [backend/.env.example](backend/.env.example).

Top ones to understand first:

- `PDF_PATH`: if missing, ingest fails.
- `FAISS_INDEX_PATH` and `FAISS_METADATA_PATH`: if missing, `/chat` cannot retrieve and returns service error.
- `EMBEDDING_PROVIDER`: if package not installed for chosen provider, startup/ingest can fail.
- `LLM_PROVIDER`: chooses answer generation backend (`template`, `ollama`, `openai`).
- `OPENAI_API_KEY`: required when provider is `openai`.
- `RETRIEVAL_MIN_SCORE`: too high can cause frequent no-context responses.
- `MAX_MESSAGE_CHARS`, `MAX_HISTORY_*`: request validation limits.

---

## 9) Typical failure scenarios and where they are handled

1. Missing index
- Trigger: index files not built.
- Location: `VectorStore.load()` in [backend/app/rag/vector_store.py](backend/app/rag/vector_store.py).
- Route response: 503 from [backend/app/api/routes_chat.py](backend/app/api/routes_chat.py).

2. Oversized request/history
- Trigger: message or history too large.
- Location: `_validate_request()` in [backend/app/services/chat_service.py](backend/app/services/chat_service.py).
- Route response: 422.

3. LLM down/unavailable
- Trigger: Ollama unreachable or OpenAI issue.
- Location: generation call in [backend/app/services/chat_service.py](backend/app/services/chat_service.py).
- Route response: custom `GitaGPTError` -> 503.

4. Poor retrieval match
- Trigger: scores below threshold.
- Location: [backend/app/rag/retriever.py](backend/app/rag/retriever.py).
- Response: graceful `insufficient_context` message, not crash.

5. LLM output quality/format issues
- Trigger: model returns malformed structure.
- Location: `_enforce_contract()` in [backend/app/rag/generator.py](backend/app/rag/generator.py).
- Behavior: fallback to `_template_answer()`.

---

## 10) One complete mini trace (example)

Imagine user asks: "I am very stressed because my deadline is near and I keep panicking."

1. `/chat` endpoint receives it.
2. Intent router likely picks `stress`.
3. Theme maps to `stress`.
4. Retriever gets top candidates, boosts stress seed verses, penalizes recent verses.
5. Selected chunks go to generator.
6. Generator creates answer through configured provider.
7. Contract checker verifies format + mechanism quality.
8. Citations are generated from those same retrieved chunks.
9. Response returns with answer + citations + provider info.

This is RAG done correctly: retrieval first, grounded generation second.

---

## 11) Final revision summary (what you should now know)

After this guide, you should be able to answer:

- What `/chat` does internally from endpoint to response.
- Why ingestion is mandatory before chat.
- Why `generator.py` is both writer and quality gate.
- How backend folders are organized and what every file does.
- Where to debug if API returns 422, 503, or insufficient context.

If you want, next step can be a second companion file with diagrams only (sequence diagram + component diagram + data flow diagram) for faster revision before interviews.
