import pytest

from app.models.chat import ConversationMessage, RetrievedChunk
from app.rag.generator import Generator


class DummySettings:
    llm_provider = "groq"

    groq_base_url = "https://api.groq.com/openai/v1"
    groq_api_key = "groq-key"
    groq_model = "llama-3.1-8b-instant"
    groq_timeout_seconds = 45

    modal_base_url = "https://api.us-west-2.modal.direct/v1"
    modal_api_key = "modal-key"
    modal_model = "zai-org/GLM-5.1-FP8"
    modal_timeout_seconds = 180

    openrouter_base_url = "https://openrouter.ai/api/v1"
    openrouter_api_key = "openrouter-key"
    openrouter_timeout_seconds = 60
    openrouter_reasoning_effort = "none"
    openrouter_reasoning_exclude = True


def _sample_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id="c1",
            chapter=2,
            verse="47",
            type="translation",
            text="Do your duty without attachment.",
            score=0.95,
            source_pages=[10],
        )
    ]


def _sample_messages() -> list[ConversationMessage]:
    return [
        ConversationMessage(role="system", content="system"),
        ConversationMessage(role="user", content="Earlier question"),
        ConversationMessage(role="assistant", content="Earlier answer"),
    ]


@pytest.mark.asyncio
async def test_fallback_moves_from_groq_to_openrouter_before_modal():
    generator = Generator(DummySettings())

    async def fake_groq(*args, **kwargs):
        raise RuntimeError("groq down")

    async def fake_openrouter_with_model_fallback(*args, **kwargs):
        from app.rag.generator import GenerationResult

        return GenerationResult(
            answer="openrouter ok",
            provider="openrouter",
            model="openai/gpt-oss-120b:free",
            attempts=["groq:llama-3.1-8b-instant", "openrouter:openai/gpt-oss-120b:free"],
        )

    async def fake_modal(*args, **kwargs):
        raise AssertionError("modal should not be called before openrouter")

    generator._groq = fake_groq  # type: ignore[method-assign]
    generator._openrouter_with_model_fallback = fake_openrouter_with_model_fallback  # type: ignore[method-assign]
    generator._modal = fake_modal  # type: ignore[method-assign]

    result = await generator._generate_with_fallback(
        messages=_sample_messages(),
        on_token=None,
        primary="groq",
    )

    assert result.answer == "openrouter ok"
    assert result.provider == "openrouter"


@pytest.mark.asyncio
async def test_openrouter_is_used_when_first_two_not_configured():
    settings = DummySettings()
    settings.groq_api_key = None
    settings.modal_api_key = ""
    settings.openrouter_api_key = "openrouter-key"
    generator = Generator(settings)

    async def fake_openrouter_with_model_fallback(*args, **kwargs):
        from app.rag.generator import GenerationResult

        return GenerationResult(
            answer="openrouter ok",
            provider="openrouter",
            model="z-ai/glm-4.5-air:free",
            attempts=["openrouter:z-ai/glm-4.5-air:free"],
        )

    generator._openrouter_with_model_fallback = fake_openrouter_with_model_fallback  # type: ignore[method-assign]

    result = await generator._generate_with_fallback(
        messages=_sample_messages(),
        on_token=None,
        primary="groq",
    )

    assert result.answer == "openrouter ok"
    assert result.attempts == ["openrouter:z-ai/glm-4.5-air:free"]


@pytest.mark.asyncio
async def test_unknown_primary_uses_default_chain_and_reports_attempts():
    settings = DummySettings()
    settings.groq_api_key = None
    settings.modal_api_key = None
    settings.openrouter_api_key = None
    generator = Generator(settings)

    with pytest.raises(RuntimeError) as exc_info:
        await generator._generate_with_fallback(
            messages=_sample_messages(),
            on_token=None,
            primary="something-else",
        )

    error_text = str(exc_info.value)
    assert "attempted=['groq', 'openrouter', 'modal']" in error_text
    assert "OPENROUTER_API_KEY" in error_text
