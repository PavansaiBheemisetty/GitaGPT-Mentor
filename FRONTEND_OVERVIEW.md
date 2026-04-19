# GitaGPT Frontend Overview

This file explains the frontend architecture, responsibilities, data flow, and failure points.

Primary frontend root: [frontend](frontend)
Main source directory: [frontend/src](frontend/src)

## 1) Stack and architecture

Frontend uses:

- Next.js 15 App Router
- React 19 + TypeScript
- Tailwind CSS + custom design tokens
- Radix UI primitives for low-level UI building blocks
- Framer Motion for transitions
- Supabase browser client for auth
- WebSocket streaming for token-by-token assistant output

Architecture style:

- Single-page chat experience rooted at app/page.tsx
- Client-side state orchestration in ChatShell component
- REST for sessions/messages management
- WebSocket for streaming assistant generation
- Markdown rendering for assistant answers and citations display

## 2) Folder and file walkthrough

## 2.1 App shell

- [frontend/src/app/layout.tsx](frontend/src/app/layout.tsx)
  - Root layout
  - Loads Inter (body) + Cinzel (heading) fonts
  - Sets metadata title and description

- [frontend/src/app/page.tsx](frontend/src/app/page.tsx)
  - Home page entry
  - Renders ChatShell only

- [frontend/src/app/globals.css](frontend/src/app/globals.css)
  - Global theme and base styles
  - Dark gradient background + subtle texture overlay
  - CSS tokens for foreground/background/card/border/accent

## 2.2 Main components

- [frontend/src/components/ChatShell.tsx](frontend/src/components/ChatShell.tsx)
  - Main orchestrator and state container
  - Handles auth hydration
  - Loads/manages sessions
  - Handles websocket streaming lifecycle
  - Drives sidebar UX, session rename/delete, and composer submission

- [frontend/src/components/ChatComposer.tsx](frontend/src/components/ChatComposer.tsx)
  - Input textarea + submit behavior
  - Enter to send, Shift+Enter for newline
  - Disables submit during stream

- [frontend/src/components/MessageList.tsx](frontend/src/components/MessageList.tsx)
  - Renders conversation list from UiMessage[]
  - Delegates each message to MessageBubble

- [frontend/src/components/MessageBubble.tsx](frontend/src/components/MessageBubble.tsx)
  - Renders user/assistant bubble variants
  - Assistant responses rendered via react-markdown + GFM
  - Shows streaming/thinking/failure states
  - Displays grounding cues based on citations/confidence

- [frontend/src/components/CitationList.tsx](frontend/src/components/CitationList.tsx)
  - Renders backend citations list
  - Opens SourceDrawer for per-citation preview

- [frontend/src/components/SourceDrawer.tsx](frontend/src/components/SourceDrawer.tsx)
  - Citation detail modal/drawer
  - Shows verse metadata and snippet text

- [frontend/src/components/EmptyState.tsx](frontend/src/components/EmptyState.tsx)
  - First-screen prompts
  - Quick starter questions

- [frontend/src/components/StreamDust.tsx](frontend/src/components/StreamDust.tsx)
  - Streaming visual effect for assistant response in-progress

## 2.3 UI primitives

- [frontend/src/components/ui/button.tsx](frontend/src/components/ui/button.tsx)
- [frontend/src/components/ui/avatar.tsx](frontend/src/components/ui/avatar.tsx)
- [frontend/src/components/ui/scroll-area.tsx](frontend/src/components/ui/scroll-area.tsx)
- [frontend/src/components/ui/textarea.tsx](frontend/src/components/ui/textarea.tsx)

These wrap Radix and utility class patterns for reusable primitives.

## 2.4 Data and integration layer

- [frontend/src/lib/api.ts](frontend/src/lib/api.ts)
  - REST wrappers:
    - listSessions
    - createSession
    - renameSession
    - deleteSession
    - listSessionMessages
    - sendChat
  - WebSocket wrapper:
    - streamChat
  - Includes safe error parsing helper for backend detail payloads

- [frontend/src/lib/types.ts](frontend/src/lib/types.ts)
  - Shared TypeScript contracts for chat/session/stream payloads
  - Mirrors backend response model shape

- [frontend/src/lib/supabase.ts](frontend/src/lib/supabase.ts)
  - Browser singleton client factory
  - Returns null if Supabase env vars are missing

- [frontend/src/lib/utils.ts](frontend/src/lib/utils.ts)
  - Utility helpers (class merging and local helpers)

## 3) ChatShell state model

Core state in ChatShell:

- user: authenticated Supabase user or null
- accessToken: Bearer token for authenticated backend routes
- sessions: list of saved chat sessions
- activeSessionId: currently selected session
- guestConversationId: UUID for unauthenticated mode
- messages: UiMessage[] timeline
- draft: current input text
- isStreaming: stream in progress flag
- error: user-facing error message
- sidebar and session-title editing state

This one component intentionally controls data flow to avoid state fragmentation.

## 4) Auth flow

Auth integration is optional and environment-driven.

When Supabase env values are present:

1. ChatShell asks Supabase for current session on mount.
2. If session exists, user + token are stored.
3. onAuthStateChange listener keeps state synchronized.
4. User can sign in via:
- Google OAuth
- Email/password
5. Token is attached to backend REST calls and websocket payload.

When Supabase env values are absent:

- getSupabaseClient returns null
- app effectively runs in guest mode
- no persisted session list

## 5) Session and message flow

Authenticated path:

1. load sessions from GET /chat/sessions
2. load messages for active session
3. create session when needed
4. rename/delete as user action
5. backend persists user and assistant turns

Guest path:

- frontend generates local conversation UUID
- chats still work through websocket/chat route
- no backend-owned persisted session list for user

## 6) Streaming flow

WebSocket endpoint: /chat/stream/ws

Frontend event handling:

- thinking: placeholder assistant message
- token: progressively updates assistant content
- done: replaces placeholder with full ChatResponse
- error: preserves draft and shows retry-safe error text

This model gives immediate response feedback and keeps UX responsive.

## 7) Contracts between frontend and backend

Key response contract in [frontend/src/lib/types.ts](frontend/src/lib/types.ts):

- ChatResponse
  - answer
  - intent/theme
  - citations
  - retrieved_chunks
  - confidence
  - warnings
  - provider

Session contracts:

- ChatSession
- StoredMessage

Stream contracts:

- thinking
- token
- done
- error

Keeping these types aligned with backend schemas is critical.

## 8) Environment variables and behavior

Frontend env vars:

- NEXT_PUBLIC_API_BASE_URL
  - base URL for REST and websocket derivation
- NEXT_PUBLIC_SUPABASE_URL
- NEXT_PUBLIC_SUPABASE_ANON_KEY

Behavior notes:

- missing API base URL falls back to http://localhost:8000
- missing Supabase vars disables auth integration gracefully

## 9) Common frontend failure points

1. Sessions fail to load
- Usually invalid/expired token, backend auth config, or CORS mismatch

2. WebSocket closes early
- Backend auth requirement mismatch, provider failure, or network disconnect

3. Stream stalls after thinking
- Backend provider latency or upstream model timeout

4. Citation panel empty
- Backend returned insufficient context or trust failure warning

5. Auth UI not appearing
- Supabase env vars not set in frontend environment

## 10) Frontend development commands

From [frontend](frontend):

- npm install
- npm run dev
- npm run lint
- npm run build

## 11) Suggested safe extension points

If you extend frontend, these are low-risk starting points:

- Add richer session filters/sorting in ChatShell sidebar
- Add citation hover previews before opening drawer
- Add message-level copy/share controls in MessageBubble
- Add retry-once for websocket transient errors
- Add accessibility polish (keyboard shortcuts, aria labels, focus traps)
