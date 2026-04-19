from typing import Literal

from pydantic import BaseModel, Field


ChunkType = Literal["translation", "purport"]


class VerseRecord(BaseModel):
    chapter: int
    verse: str
    title: str | None = None
    translation: str | None = None
    purport: str | None = None
    source_pages: list[int] = Field(default_factory=list)
    extraction_warnings: list[str] = Field(default_factory=list)


class ChunkRecord(BaseModel):
    chunk_id: str
    chapter: int
    verse: str
    type: ChunkType
    text: str
    source_pages: list[int] = Field(default_factory=list)
    char_start: int = 0
    char_end: int = 0
    token_estimate: int = 0
