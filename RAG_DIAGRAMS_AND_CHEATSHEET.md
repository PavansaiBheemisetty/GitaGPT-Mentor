# GitaGPT Backend Diagrams and Cheat Sheet

Fast companion to [RAG_FLOW_FROM_SCRATCH.md](RAG_FLOW_FROM_SCRATCH.md).

Use this file when you want visual recall in minutes.

## 1) POST /chat sequence

```mermaid
sequenceDiagram
    autonumber
    participant U as Client
    participant API as routes_chat /chat
    participant D as deps
    participant S as ChatService
    participant I as intent_router
    participant M as session_memory
    participant R as Retriever
    participant V as VectorStore
    participant G as Generator
    participant C as citations
    participant DB as ChatRepository

    U->>API: POST /chat
    API->>D: get_optional_user + get_chat_service
    D-->>API: user?, cached service
    API->>S: chat(request, user)
    S->>S: _validate_request
    S->>S: _resolve_history_and_summary
    S->>I: classify_query_intent

    alt out_of_scope
        S->>DB: persist fallback turn (if enabled)
        S-->>API: ChatResponse(insufficient)
        API-->>U: safe response
    else in_scope
        S->>M: recent_verses(conversation_id)
        S->>R: retrieve(query, theme, avoid_verses)
        R->>V: search(query_vector)
        V-->>R: candidates
        R->>R: rerank + diverse select + threshold
        R-->>S: chunks

        alt no chunks
            S->>DB: persist fallback turn (if enabled)
            S-->>API: ChatResponse(insufficient_context)
            API-->>U: fallback
        else chunks found
            S->>G: generate(question, chunks, intent, theme)
            G->>G: provider call (modal/groq/openai/template)
            G->>G: _enforce_contract
            G-->>S: final answer
            S->>C: backend_citations
            C-->>S: citations
            S->>M: remember verses
            S->>DB: persist user + assistant turns
            S-->>API: ChatResponse(sufficient)
            API-->>U: answer + citations + provider
        end
    end
```

## 2) WS /chat/stream/ws sequence

```mermaid
sequenceDiagram
    autonumber
    participant UI as Frontend
    participant WS as routes_chat websocket
    participant A as SupabaseAuthService
    participant S as ChatService

    UI->>WS: connect /chat/stream/ws
    UI->>WS: payload(message, conversation_id, access_token)
    WS->>A: resolve_user(access_token)

    alt auth required and missing user
        WS-->>UI: error
        WS-->>UI: close
    else accepted
        WS-->>UI: thinking
        WS->>S: chat(..., on_token=callback)
        loop while generating
            S-->>WS: token
            WS-->>UI: token event
        end
        WS-->>UI: done(response)
    end
```

## 3) Runtime component map

```mermaid
flowchart LR
    A[FastAPI] --> B[API routes]
    B --> C[Deps layer]
    C --> D[ChatService]

    D --> E[Intent router]
    D --> F[Retriever]
    F --> G[Embedding provider]
    F --> H[VectorStore]
    D --> I[Generator]
    I --> J[Prompt builder]
    I --> K[LLM provider]
    D --> L[Citation builder]
    D --> M[ConversationVerseMemory]

    C --> N[SupabaseAuthService]
    C --> O[ChatRepository]

    O --> P[(Postgres)]
    H --> Q[(faiss.index)]
    H --> R[(metadata.json)]
```

## 4) Ingestion map

```mermaid
flowchart TD
    A[PDF_PATH] --> B[pdf_loader.extract_pdf_pages]
    B --> C[parser.parse_verses]
    C --> D[corpus_report.build_corpus_report]
    D --> E[enforce_corpus_gates]
    E --> F[chunker.chunk_verses]
    F --> G[write verses.jsonl/chunks.jsonl]
    G --> H[embeddings.create_embedding_provider]
    H --> I[embed chunk texts]
    I --> J[vector_store.build]
    J --> K[data/index/faiss.index + metadata.json]
```

## 5) Quick file recall

- [backend/app/api/routes_chat.py](backend/app/api/routes_chat.py): chat + sessions + websocket
- [backend/app/api/deps.py](backend/app/api/deps.py): auth and service wiring
- [backend/app/services/chat_service.py](backend/app/services/chat_service.py): end-to-end orchestration
- [backend/app/services/chat_repository.py](backend/app/services/chat_repository.py): DB persistence
- [backend/app/services/auth_service.py](backend/app/services/auth_service.py): Supabase user lookup
- [backend/app/rag/retriever.py](backend/app/rag/retriever.py): retrieve/rerank/diversify
- [backend/app/rag/generator.py](backend/app/rag/generator.py): provider routing + contract gate
- [backend/app/rag/prompt.py](backend/app/rag/prompt.py): prompt assembly
- [backend/app/models/chat.py](backend/app/models/chat.py): request/response/session/stream contracts
- [backend/sql/chat_schema.sql](backend/sql/chat_schema.sql): SQL schema for persistence tables + indexes

## 5.1 Route checklist (including new additions)

- POST /chat
- GET /chat/sessions
- POST /chat/sessions
- PATCH /chat/sessions/{session_id}
- DELETE /chat/sessions/{session_id}
- DELETE /sessions/{session_id} (compat alias)
- GET /chat/sessions/{session_id}/messages
- WS /chat/stream/ws

## 6) Function cheat sheet

### ChatService

- chat: complete request pipeline
- _resolve_history_and_summary: memory enrichment from DB
- _build_memory_context: compacts recent turns for prompt
- _persist_turn: writes message rows and summary

### deps.py

- get_optional_user: parses/validates Bearer token
- get_current_user: enforced auth dependency
- get_chat_service/get_chat_repository/get_auth_service: cached service graph

### Retriever

- retrieve: candidate search and filtering
- _rerank: semantic score shaping
- _select_diverse: verse/type diversity enforcement

### Generator

- generate: provider dispatch
- _generate_with_modal_fallback: modal then groq
- _modal/_groq/_openai: provider adapters
- _template_answer: deterministic fallback
- _enforce_contract: output quality gate

### ChatRepository

- ensure_session: creates session lazily and upgrades placeholder title
- rename_session/delete_session: authenticated ownership-checked mutations
- list_messages: ownership-gated read of stored transcript
- refresh_summary: keeps session summary fresh from latest turns

## 7) Debug decision tree

```mermaid
flowchart TD
    A[Issue] --> B{Category}

    B -->|503 vector index missing| C[Run backend/scripts/ingest.py]
    B -->|422 validation| D[Check MAX_MESSAGE_CHARS and MAX_HISTORY_*]
    B -->|Session API failing| E[Check DATABASE_URL and DB reachability]
    B -->|401 auth| F[Check Bearer token from Supabase session]
    B -->|Rename/Delete 404| J[Verify session belongs to current user]
    B -->|WS auth_required failure| K[Send valid access_token or disable AUTH_REQUIRED]
    B -->|Provider unavailable| G[Check MODAL/GROQ/OPENAI keys and model names]
    B -->|Weak answer| H[Check retrieval score threshold and chunk quality]
    B -->|Streaming interrupted| I[Inspect websocket error events + backend logs]
```

## 8) One-line memory hook

V I R G V C P R

Validate -> Intent -> Retrieve -> Generate -> Verify -> Cite -> Persist -> Return
