from app.models.chat import ChatMessage
from app.services.memory_builder import SessionMemoryBuilder


def test_memory_builder_keeps_full_history_when_small() -> None:
    builder = SessionMemoryBuilder(max_chars=1000, summary_max_chars=300, recent_message_count=4)

    result = builder.build(
        system_prompt="system prompt",
        history=[
            ChatMessage(role="user", content="I failed an interview."),
            ChatMessage(role="assistant", content="See the setback clearly and act again."),
        ],
        current_prompt="What should I do now?",
    )

    assert result.truncated is False
    assert [message.role for message in result.messages] == ["system", "user", "assistant", "user"]


def test_memory_builder_summarizes_old_messages_when_large() -> None:
    builder = SessionMemoryBuilder(max_chars=220, summary_max_chars=100, recent_message_count=2)

    history = [
        ChatMessage(role="user", content="First long reflection about interview rejection and fear."),
        ChatMessage(role="assistant", content="First answer about detachment and disciplined action."),
        ChatMessage(role="user", content="Second long reflection about parents, pressure, and comparison."),
        ChatMessage(role="assistant", content="Second answer about svadharma and steadiness."),
    ]

    result = builder.build(
        system_prompt="system prompt",
        history=history,
        current_prompt="What should I do now?",
    )

    assert result.truncated is True
    assert result.summary is not None
    assert result.messages[1].role == "system"
    assert "Conversation summary of earlier turns" in result.messages[1].content
