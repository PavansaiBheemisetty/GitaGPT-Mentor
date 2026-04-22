from dataclasses import dataclass
import json
from typing import Iterable

import httpx


@dataclass(frozen=True, slots=True)
class LlmTarget:
    provider: str
    model: str

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


OPENROUTER_FALLBACK_CHAIN: tuple[LlmTarget, ...] = (
    LlmTarget(provider="openrouter", model="z-ai/glm-4.5-air:free"),
    LlmTarget(provider="openrouter", model="openai/gpt-oss-120b:free"),
    LlmTarget(provider="openrouter", model="mistralai/mistral-nemo:exacto"),
    LlmTarget(provider="openrouter", model="nvidia/nemotron-3-super-120b-a12b:free"),
    LlmTarget(provider="openrouter", model="meta-llama/llama-3-8b-instruct:nitro"),
)

RETRYABLE_ERROR_MARKERS = (
    "rate limit",
    "rate_limit",
    "timeout",
    "timed out",
    "quota exceeded",
    "provider unavailable",
    "service unavailable",
    "temporarily unavailable",
    "upstream",
)


def openrouter_fallback_chain() -> tuple[LlmTarget, ...]:
    return OPENROUTER_FALLBACK_CHAIN


def is_retryable_provider_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        if response is None:
            return True
        if response.status_code in {408, 409, 425, 429}:
            return True
        if 500 <= response.status_code <= 599:
            return True
        return _contains_retryable_marker(_response_text_variants(response))

    if isinstance(exc, httpx.RequestError):
        return _contains_retryable_marker((str(exc),))

    return _contains_retryable_marker((str(exc),))


def _contains_retryable_marker(values: Iterable[str]) -> bool:
    haystack = " ".join(value.lower() for value in values if value).strip()
    return any(marker in haystack for marker in RETRYABLE_ERROR_MARKERS)


def _response_text_variants(response: httpx.Response) -> tuple[str, ...]:
    raw = (response.text or "").strip()
    values = [raw]
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        return tuple(values)

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            for key in ("message", "code", "type"):
                value = error.get(key)
                if value:
                    values.append(str(value))
        for key in ("message", "detail"):
            value = payload.get(key)
            if value:
                values.append(str(value))
    return tuple(values)
