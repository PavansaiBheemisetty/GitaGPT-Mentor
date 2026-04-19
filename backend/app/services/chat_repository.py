import asyncio
import json
import uuid
from dataclasses import dataclass

import asyncpg
from pydantic import ValidationError

from app.models.chat import ChatMessage, SessionSummary, StoredMessage


@dataclass(slots=True)
class AuthUser:
    id: str
    email: str


class ChatRepository:
    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None
        self._pool_lock = asyncio.Lock()
        self._schema_ready = False

    @property
    def enabled(self) -> bool:
        return bool(self._database_url)

    async def _get_pool(self) -> asyncpg.Pool:
        if not self._database_url:
            raise RuntimeError("DATABASE_URL is not configured.")
        if self._pool:
            return self._pool
        async with self._pool_lock:
            if self._pool is None:
                self._pool = await asyncpg.create_pool(
                    self._database_url,
                    ssl="require",
                    min_size=1,
                    max_size=8,
                    statement_cache_size=0
                )
            if not self._schema_ready:
                await self._ensure_schema(self._pool)
                self._schema_ready = True
        return self._pool

    async def _ensure_schema(self, pool: asyncpg.Pool) -> None:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id UUID PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    summary TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id BIGSERIAL PRIMARY KEY,
                    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    request_id TEXT,
                    response_payload JSONB,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                ALTER TABLE messages
                ADD COLUMN IF NOT EXISTS response_payload JSONB;

                CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated
                    ON chat_sessions(user_id, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_messages_session_timestamp
                    ON messages(session_id, timestamp ASC);
                """
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._schema_ready = False

    async def ensure_user(self, user: AuthUser) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, email)
                VALUES ($1::uuid, $2)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """,
                user.id,
                user.email,
            )

    async def create_session(self, user: AuthUser, title: str | None = None) -> SessionSummary:
        pool = await self._get_pool()
        await self.ensure_user(user)
        session_id = str(uuid.uuid4())
        safe_title = (title or "New Chat").strip()[:120] or "New Chat"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO chat_sessions (id, user_id, title)
                VALUES ($1::uuid, $2::uuid, $3)
                RETURNING id::text, user_id::text, title, summary,
                          created_at::text AS created_at,
                          updated_at::text AS updated_at
                """,
                session_id,
                user.id,
                safe_title,
            )
        return SessionSummary(**dict(row))

    async def ensure_session(self, user: AuthUser, session_id: str, first_message: str) -> None:
        pool = await self._get_pool()
        await self.ensure_user(user)
        title = self._title_from_first_message(first_message)
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                """
                SELECT title
                FROM chat_sessions
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                session_id,
                user.id,
            )
            if existing:
                current_title = str(existing["title"] or "").strip()
                if self._is_placeholder_title(current_title):
                    await conn.execute(
                        """
                        UPDATE chat_sessions
                        SET title = $1, updated_at = NOW()
                        WHERE id = $2::uuid AND user_id = $3::uuid
                        """,
                        title,
                        session_id,
                        user.id,
                    )
                return
            await conn.execute(
                """
                INSERT INTO chat_sessions (id, user_id, title)
                VALUES ($1::uuid, $2::uuid, $3)
                """,
                session_id,
                user.id,
                title,
            )

    async def list_sessions(self, user_id: str) -> list[SessionSummary]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id::text, user_id::text, title, summary,
                       created_at::text AS created_at,
                       updated_at::text AS updated_at
                FROM chat_sessions
                WHERE user_id = $1::uuid
                ORDER BY updated_at DESC
                LIMIT 150
                """,
                user_id,
            )
        return [SessionSummary(**dict(row)) for row in rows]

    async def list_messages(self, user_id: str, session_id: str) -> list[StoredMessage]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            owner = await conn.fetchval(
                """
                SELECT 1
                FROM chat_sessions
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                session_id,
                user_id,
            )
            if not owner:
                return []
            rows = await conn.fetch(
                """
                SELECT id, session_id::text, role, content, request_id, response_payload,
                       timestamp::text AS timestamp
                FROM messages
                WHERE session_id = $1::uuid
                ORDER BY timestamp ASC
                LIMIT 2000
                """,
                session_id,
            )
        return [self._map_stored_message(row) for row in rows]

    async def load_recent_history(self, user_id: str, session_id: str, limit: int) -> list[ChatMessage]:
        pool = await self._get_pool()
        safe_limit = max(1, min(limit, 20))
        async with pool.acquire() as conn:
            owner = await conn.fetchval(
                """
                SELECT 1
                FROM chat_sessions
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                session_id,
                user_id,
            )
            if not owner:
                return []
            rows = await conn.fetch(
                """
                SELECT role, content
                FROM messages
                WHERE session_id = $1::uuid
                ORDER BY timestamp DESC
                LIMIT $2
                """,
                session_id,
                safe_limit,
            )
        return [ChatMessage(role=row["role"], content=row["content"]) for row in reversed(rows)]

    async def session_summary(self, user_id: str, session_id: str) -> str | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT summary
                FROM chat_sessions
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                session_id,
                user_id,
            )

    async def append_message(
        self,
        *,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        request_id: str | None = None,
        response_payload: dict | None = None,
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            owner = await conn.fetchval(
                """
                SELECT 1
                FROM chat_sessions
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                session_id,
                user_id,
            )
            if not owner:
                raise ValueError("session not found for this user")
            response_json = json.dumps(response_payload) if response_payload is not None else None
            await conn.execute(
                """
                INSERT INTO messages (session_id, role, content, request_id, response_payload)
                VALUES ($1::uuid, $2, $3, $4, $5::jsonb)
                """,
                session_id,
                role,
                content,
                request_id,
                response_json,
            )
            await conn.execute(
                """
                UPDATE chat_sessions
                SET updated_at = NOW()
                WHERE id = $1::uuid
                """,
                session_id,
            )

    async def refresh_summary(self, user_id: str, session_id: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            owner = await conn.fetchval(
                """
                SELECT 1
                FROM chat_sessions
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                session_id,
                user_id,
            )
            if not owner:
                return
            rows = await conn.fetch(
                """
                SELECT role, content
                FROM messages
                WHERE session_id = $1::uuid
                ORDER BY timestamp DESC
                LIMIT 6
                """,
                session_id,
            )
            if not rows:
                return
            compact_lines = []
            for row in reversed(rows):
                role = "User" if row["role"] == "user" else "Assistant"
                snippet = " ".join(str(row["content"]).split())[:160]
                compact_lines.append(f"{role}: {snippet}")
            summary = "\n".join(compact_lines)[:1400]
            await conn.execute(
                """
                UPDATE chat_sessions
                SET summary = $1,
                    updated_at = NOW()
                WHERE id = $2::uuid
                """,
                summary,
                session_id,
            )

    async def rename_session(self, user_id: str, session_id: str, title: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            owner = await conn.fetchval(
                """
                SELECT 1
                FROM chat_sessions
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                session_id,
                user_id,
            )
            if not owner:
                raise ValueError("session not found for this user")
            await conn.execute(
                """
                UPDATE chat_sessions
                SET title = $1, updated_at = NOW()
                WHERE id = $2::uuid AND user_id = $3::uuid
                """,
                title,
                session_id,
                user_id,
            )

    async def delete_session(self, user_id: str, session_id: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            owner = await conn.fetchval(
                """
                SELECT 1
                FROM chat_sessions
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                session_id,
                user_id,
            )
            if not owner:
                raise ValueError("session not found for this user")
            await conn.execute(
                """
                DELETE FROM chat_sessions
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                session_id,
                user_id,
            )

    @staticmethod
    def _title_from_first_message(message: str) -> str:
        compact = " ".join(message.split())
        if not compact:
            return "New Chat"
            
        stopwords = {
            "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
            "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", 
            "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", 
            "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", 
            "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", 
            "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", 
            "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", 
            "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", 
            "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", 
            "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", 
            "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", 
            "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now"
        }
        
        words = [w for w in compact.split() if w.lower().strip("?!.,;:'\"") not in stopwords]
        
        title_words = words[:5]
        if not title_words:
            title_words = compact.split()[:5]

        title_str = " ".join(title_words).strip("?!.,;:'\"")
        if not title_str:
            return "New Chat"
            
        return title_str[0].upper() + title_str[1:]

    @staticmethod
    def _is_placeholder_title(title: str) -> bool:
        normalized = title.strip().lower()
        return normalized in {"", "new chat", "untitled", "untitled chat", "new conversation"}

    @staticmethod
    def _map_stored_message(row: asyncpg.Record) -> StoredMessage:
        payload = dict(row)
        raw_response = payload.pop("response_payload", None)

        parsed_response = raw_response
        if isinstance(raw_response, str):
            try:
                parsed_response = json.loads(raw_response)
            except json.JSONDecodeError:
                parsed_response = None

        payload["response"] = parsed_response
        try:
            return StoredMessage(**payload)
        except ValidationError:
            # Keep message history readable even if legacy payload shape cannot be parsed.
            payload["response"] = None
            return StoredMessage(**payload)
