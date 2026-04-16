# Agent Instructions

Use this file as the primary coding-agent guide for this repository.

## Core References

- Product and setup: [README.md](README.md)
- Planning context and deferred scope: [TODOS.md](TODOS.md)
- gstack slash-command catalog: [.github/copilot-instructions.md](.github/copilot-instructions.md)

Link to docs for details instead of duplicating large sections here.

## Repository Shape

- Backend API and RAG pipeline: [backend/app](backend/app)
- Ingestion and corpus tooling: [backend/scripts](backend/scripts)
- Backend tests: [backend/tests](backend/tests)
- Frontend app and UI: [frontend/src](frontend/src)

## Common Commands

Run from repository root unless noted.

1. Backend setup:
	- cd backend
	- python3 -m venv .venv
	- . .venv/bin/activate
	- pip install -e ".[dev]"
2. Optional full RAG deps:
	- pip install -e ".[dev,rag,openai]"
3. Frontend setup:
	- cd frontend
	- npm install
4. Build index:
	- cd backend
	- python scripts/ingest.py
5. Run backend:
	- cd backend
	- uvicorn app.main:app --reload
6. Run frontend:
	- cd frontend
	- npm run dev
7. Verify:
	- cd backend && pytest
	- cd frontend && npm run lint

## Project Conventions

- Keep backend and frontend changes scoped. Avoid cross-layer refactors unless required by the task.
- Preserve grounded-answer guarantees: backend-owned citations and retrieval-first answers.
- Do not commit local corpus artifacts or source PDFs in backend/data.
- Prefer minimal diffs and keep public API shapes stable unless the request explicitly changes them.
- If the user invokes a slash command such as /review or /qa, load and follow the matching SKILL.md from the gstack skill path exactly.

## Common Pitfalls

- Missing index files will break chat routes; run backend/scripts/ingest.py before diagnosing retrieval failures.
- If FAISS or sentence-transformers cannot be installed, use the local fallback provider settings documented in [README.md](README.md).
- Frontend calls backend using NEXT_PUBLIC_API_BASE_URL; ensure local URLs and CORS are aligned.