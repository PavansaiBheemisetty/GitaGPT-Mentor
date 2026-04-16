from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["user", "assistant"]
Confidence = Literal["sufficient", "insufficient", "error"]


class ChatMessage(BaseModel):
    role: Role
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    top_k: int | None = Field(default=None, ge=1, le=12)


class Citation(BaseModel):
    chapter: int
    verse: str
    type: str
    chunk_id: str
    source_pages: list[int] = Field(default_factory=list)
    preview: str | None = None
    score: float | None = None


class RetrievedChunk(BaseModel):
    chunk_id: str
    chapter: int
    verse: str
    type: str
    text: str
    score: float
    source_pages: list[int] = Field(default_factory=list)

    @property
    def preview(self) -> str:
        return self.text[:280].strip()


class ProviderInfo(BaseModel):
    embedding: str
    llm: str


class ChatResponse(BaseModel):
    request_id: str
    answer: str
    intent: str | None = None
    theme: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    confidence: Confidence
    warnings: list[str] = Field(default_factory=list)
    provider: ProviderInfo
