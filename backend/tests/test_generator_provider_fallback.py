import pytest

from app.models.chat import RetrievedChunk
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
    openrouter_model = "meta-llama/llama-3.1-8b-instruct:free"
    openrouter_timeout_seconds = 60


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


@pytest.mark.asyncio
async def test_fallback_moves_from_groq_to_openrouter_before_modal():
    generator = Generator(DummySettings())

    async def fake_groq(*args, **kwargs):
        raise RuntimeError("groq down")

    async def fake_openrouter(*args, **kwargs):
        return "openrouter ok"

    async def fake_modal(*args, **kwargs):
        raise AssertionError("modal should not be called before openrouter")

    generator._groq = fake_groq  # type: ignore[method-assign]
    generator._openrouter = fake_openrouter  # type: ignore[method-assign]
    generator._modal = fake_modal  # type: ignore[method-assign]

    result = await generator._generate_with_fallback(
        "What is my duty?",
        _sample_chunks(),
        intent="dharma_conflict",
        theme="dharma_conflict",
        avoid_verses=[],
        memory_context=None,
        on_token=None,
        primary="groq",
    )

    assert result == "openrouter ok"


@pytest.mark.asyncio
async def test_openrouter_is_used_when_first_two_not_configured():
    settings = DummySettings()
    settings.groq_api_key = None
    settings.modal_api_key = ""
    settings.openrouter_api_key = "openrouter-key"
    generator = Generator(settings)

    async def fake_openrouter(*args, **kwargs):
        return "openrouter ok"

    generator._openrouter = fake_openrouter  # type: ignore[method-assign]

    result = await generator._generate_with_fallback(
        "Help me stay calm",
        _sample_chunks(),
        intent="stress",
        theme="stress",
        avoid_verses=[],
        memory_context=None,
        on_token=None,
        primary="groq",
    )

    assert result == "openrouter ok"


@pytest.mark.asyncio
async def test_unknown_primary_uses_default_chain_and_reports_attempts():
    settings = DummySettings()
    settings.groq_api_key = None
    settings.modal_api_key = None
    settings.openrouter_api_key = None
    generator = Generator(settings)

    with pytest.raises(RuntimeError) as exc_info:
        await generator._generate_with_fallback(
            "Why am I restless?",
            _sample_chunks(),
            intent="focus",
            theme="focus",
            avoid_verses=[],
            memory_context=None,
            on_token=None,
            primary="something-else",
        )

    error_text = str(exc_info.value)
    assert "attempted=['groq', 'openrouter', 'modal']" in error_text
    assert "OPENROUTER_API_KEY" in error_text
