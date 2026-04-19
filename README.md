# 🧠 GitaGPT

**A context-aware AI mentor grounded in the Bhagavad Gita, built with intent routing, theme-aware retrieval, and structured guidance generation.**

---

## 🚀 Overview

GitaGPT is not a generic quote bot. It is a **reasoning-oriented RAG system** designed for real human situations: pressure, anger, loss, confusion, comparison, and meaning.

Instead of doing plain retrieve-then-summarize, it runs a multi-stage pipeline:

- classify intent
- map to the right philosophical lens
- retrieve and rerank context
- generate a structured answer
- validate response quality and fit

---

## 📘 Documentation Guides

- Backend deep dive: [RAG_FLOW_FROM_SCRATCH.md](RAG_FLOW_FROM_SCRATCH.md)
- Backend visual cheat-sheet: [RAG_DIAGRAMS_AND_CHEATSHEET.md](RAG_DIAGRAMS_AND_CHEATSHEET.md)
- Frontend architecture guide: [FRONTEND_OVERVIEW.md](FRONTEND_OVERVIEW.md)

---

## ✨ Key Features

### 🔍 1. Intent Classification Layer

The backend classifies queries before retrieval. It supports both broad themes and emotional-state nuance:

- grief_loss (irreversible death-related grief)
- emotional_low (heartbreak, loneliness, rejection)
- emotional_high (success highs, ego drift)
- performance_context (exam, interview, career performance)
- stress
- anger
- peace
- failure
- existential
- focus
- out_of_scope detection

This keeps retrieval and generation aligned with what the user is actually experiencing.

---

### 🧠 2. Theme-Based Reasoning

Intent is mapped to a theme with verse priorities and a dedicated reasoning lens.

| Intent | Theme Lens | Priority Verses |
| --- | --- | --- |
| Grief Loss | Finality + continuity + compassionate meaning-making | BG 2.13, 2.20 |
| Emotional Low | Attachment pain and gentle detachment | BG 2.62, 2.63, 2.70, 2.71 |
| Emotional High | Balance in success, humility in action | BG 2.48, 2.57, 2.64 |
| Performance Context | Disciplined effort over result obsession | BG 2.47, 2.50, 6.5 |
| Stress | Equanimity under pressure | BG 2.14, 2.56, 6.26 |
| Anger | Desire → attachment → anger chain | BG 2.62, 2.63, 3.37 |
| Peace | Detachment from craving and egoic ownership | BG 2.71, 5.29, 18.66 |
| Failure | Duty without identity collapse | BG 2.47, 2.38 |
| Existential | Self-upliftment and purpose | BG 6.5, 18.66 |
| Focus | Repeated redirection of the mind | BG 6.5, 6.26 |

---

### 📚 3. Retrieval-Augmented Generation (RAG)

- Embeddings: `BAAI/bge-base-en-v1.5` via sentence-transformers (or OpenAI/hash fallback)
- Vector store: FAISS (or simple local fallback)
- Theme-seed reranking with verse boosts
- Diversity-aware selection across translation and purport chunks
- Recent-verse memory to reduce repetitive citations in a conversation

### 🔐 4. Authenticated Sessions and Persistence

- Supabase Auth (Google + email magic-link)
- User-scoped chat sessions with persistent history in PostgreSQL
- Session summaries refreshed as new turns arrive
- Same account always loads the same chats

### ⚡ 5. Real-Time Streaming Chat

- WebSocket endpoint streams assistant output token-by-token
- UI shows Thinking -> Streaming -> Done transitions
- Resilient retry UX preserves the user draft on failure

---

### 🧩 6. Structured Response Engine

Every answer is built to follow this format:

1. Direct Insight (Human Tone)
2. Gita Wisdom (Verse Reference + Meaning)
3. Why This Happens (Mechanism)
4. Practical Reflection (Actionable Steps)

Then a one-line closing takeaway.

This keeps output useful, readable, and consistent.

---

### 🛡️ 7. Guardrails and Validation

- Enforced section structure
- Word-range checks
- Theme-mechanism compatibility checks
- Action-step validity checks
- Real-life context checks
- Post-processing for bullet consistency and cleanup
- Deterministic template fallback when provider output fails contract

---

### 🚫 8. Out-of-Scope Handling

The system avoids forcing Gita guidance onto unrelated factual requests.

Example:

> “What is the capital of Japan?”
> → graceful scope redirection, not hallucinated philosophy

---

## 🏗️ Architecture

```text
User Query
		↓
Intent Classification
		↓
Intent → Theme Mapping
		↓
Retriever (Embeddings + Vector Store + Rerank)
		↓
LLM Generation (Modal / Groq fallback / OpenAI / Template)
		↓
Contract Validation Layer
		↓
Final Structured Output + Backend-Owned Citations
```

---

## 📁 Repository Layout

```text
backend/
	app/
		api/          # FastAPI routes
		rag/          # intent routing, theme routing, retrieval, generation
		services/     # chat orchestration
	scripts/        # ingest and inspection tools
	tests/          # backend tests

frontend/
	src/app/        # Next.js app shell
	src/components/ # chat UI components
	src/lib/        # API client and types
```

---

## ⚙️ Tech Stack

- Backend: FastAPI + Pydantic + httpx
- Frontend: Next.js 15 + React 19 + TypeScript
- Embeddings: BGE (`sentence-transformers`) / OpenAI / hash fallback
- Vector search: FAISS / simple local store
- Generation: Modal (primary) / Groq fallback / OpenAI / deterministic template fallback

---

## 🛠️ Quickstart

### 1) Backend setup

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

For full RAG + OpenAI extras:

```bash
pip install -e ".[dev,rag,openai]"
```

### 2) Frontend setup

```bash
cd ../frontend
npm install
```

### 3) Add source PDF

```bash
cd ..
mkdir -p backend/data/raw
cp "Bhagavad-Gita As It Is.pdf" "backend/data/raw/Bhagavad-Gita As It Is.pdf"
```

Or set `PDF_PATH` in `backend/.env`.

### 4) Inspect extraction

```bash
cd backend
. .venv/bin/activate
python scripts/inspect_corpus.py --pages 10 --output data/fixtures/local/extraction-sample.txt
```

### 5) Build corpus and index

```bash
python scripts/ingest.py
```

### 6) Run backend

```bash
uvicorn app.main:app --reload
```

### 6.1) Apply chat schema (required for persistence)

Run SQL from `backend/sql/chat_schema.sql` in Supabase SQL editor (or your PostgreSQL instance).

### 6.2) Configure backend env

Copy `backend/.env.example` to `backend/.env` and set:

- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- Optional: `AUTH_REQUIRED=true` to block unauthenticated chat calls

### 7) Run frontend

```bash
cd ../frontend
npm run dev
```

Copy `frontend/.env.example` to `frontend/.env.local` and set:

- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

Open http://localhost:3000.

## 🗃️ Database Schema

`backend/sql/chat_schema.sql` creates:

- `users`
- `chat_sessions`
- `messages`

Each session is user-owned, messages are session-owned, and summaries are maintained on `chat_sessions.summary`.

## 🔌 API Surface

- `POST /chat` (classic non-stream response)
- `GET /chat/sessions` (authenticated)
- `POST /chat/sessions` (authenticated)
- `GET /chat/sessions/{session_id}/messages` (authenticated)
- `WS /chat/stream/ws` (streaming events: `thinking`, `token`, `done`, `error`)

---

## 🔌 Provider Modes

### Embeddings

- `EMBEDDING_PROVIDER=sentence-transformers`
- `EMBEDDING_PROVIDER=openai`
- `EMBEDDING_PROVIDER=hash` (local deterministic fallback)

### LLM

- `LLM_PROVIDER=modal`
- `LLM_PROVIDER=groq`
- `LLM_PROVIDER=openai`
- `LLM_PROVIDER=template` (deterministic fallback)

If native ML dependencies are unavailable:

```text
EMBEDDING_PROVIDER=hash
VECTOR_STORE_PROVIDER=simple
LLM_PROVIDER=template
```

---

## ✅ Quality and Safety Principles

- Backend owns citations, model citations are never trusted blindly.
- Ingestion enforces corpus quality gates before indexing.
- `/chat` validates input size and history bounds.
- Missing or weak retrieval context returns safe fallback responses.
- Out-of-scope prompts are redirected cleanly.

---

## 🧪 Testing

Run backend tests:

```bash
cd backend
pytest
```

Run frontend lint:

```bash
cd frontend
npm run lint
```

---

## 📌 Example Use Cases

- Managing stress during deadlines and interviews
- Handling anger in relationships and conflict
- Working through grief and irreversible loss
- Recovering from rejection or failure
- Rebuilding focus and disciplined routines
- Finding direction in existential low phases

---

## 🛣️ Roadmap

- Memory-aware personalization per user
- Multi-turn follow-up reasoning layer
- Stronger automated evaluation harness
- UI enhancements for longitudinal reflection
- Voice-first interaction mode

---

## 🤝 Contributing

Contributions are welcome.

High-impact areas:

- better intent and emotional-state routing
- improved retrieval/reranking strategies
- stronger evaluation suites
- frontend UX and accessibility improvements

---

## 🙏 Acknowledgment

Inspired by timeless wisdom from the Bhagavad Gita, reinterpreted through modern AI system design.

---

## ⭐ Final Note

GitaGPT is a step toward AI systems that are not just informative, but thoughtful, context-aware, and emotionally aligned.
