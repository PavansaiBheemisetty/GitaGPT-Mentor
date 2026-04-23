from dataclasses import dataclass

from app.models.chat import ChatMessage, ConversationMessage


@dataclass(slots=True)
class MemoryBuildResult:
    messages: list[ConversationMessage]
    summary: str | None
    full_history_count: int
    truncated: bool


class SessionMemoryBuilder:
    def __init__(
        self,
        *,
        max_chars: int = 14000,
        summary_max_chars: int = 1800,
        recent_message_count: int = 8,
    ) -> None:
        self.max_chars = max_chars
        self.summary_max_chars = summary_max_chars
        self.recent_message_count = recent_message_count

    def build(
        self,
        *,
        system_prompt: str,
        history: list[ChatMessage],
        current_prompt: str = "",
    ) -> MemoryBuildResult:
        normalized_history = self._normalize_history(history)
        base_messages = [ConversationMessage(role="system", content=system_prompt)]
        base_chars = len(system_prompt) + len(current_prompt)
        history_chars = sum(len(item.content) for item in normalized_history)
        current_prompt_message = (
            [ConversationMessage(role="user", content=current_prompt)] if current_prompt.strip() else []
        )

        if base_chars + history_chars <= self.max_chars:
            return MemoryBuildResult(
                messages=[
                    *base_messages,
                    *[ConversationMessage(role=item.role, content=item.content) for item in normalized_history],
                    *current_prompt_message,
                ],
                summary=None,
                full_history_count=len(normalized_history),
                truncated=False,
            )

        recent_history = normalized_history[-self.recent_message_count :]
        summary_source = normalized_history[: max(0, len(normalized_history) - len(recent_history))]
        summary = self._summarize(summary_source)
        summary_message = (
            [ConversationMessage(role="system", content=f"Conversation summary of earlier turns:\n{summary}")]
            if summary
            else []
        )
        messages = [
            *base_messages,
            *summary_message,
            *[ConversationMessage(role=item.role, content=item.content) for item in recent_history],
            *current_prompt_message,
        ]

        while self._messages_char_count(messages) > self.max_chars and len(recent_history) > 2:
            recent_history = recent_history[1:]
            messages = [
                *base_messages,
                *summary_message,
                *[ConversationMessage(role=item.role, content=item.content) for item in recent_history],
                *current_prompt_message,
            ]

        return MemoryBuildResult(
            messages=messages,
            summary=summary,
            full_history_count=len(normalized_history),
            truncated=True,
        )

    def _normalize_history(self, history: list[ChatMessage]) -> list[ChatMessage]:
        normalized: list[ChatMessage] = []
        previous_role: str | None = None
        for item in history:
            content = item.content.strip()
            if not content:
                continue
            role = item.role
            if role == previous_role:
                merged = normalized[-1]
                merged.content = f"{merged.content}\n\n{content}"
                continue
            normalized.append(ChatMessage(role=role, content=content))
            previous_role = role
        return normalized

    def _summarize(self, messages: list[ChatMessage]) -> str | None:
        if not messages:
            return None
        lines: list[str] = []
        budget = self.summary_max_chars
        for item in messages:
            speaker = "User" if item.role == "user" else "Assistant"
            compact = " ".join(item.content.split())
            line = f"- {speaker}: {compact[:220]}"
            if sum(len(entry) for entry in lines) + len(line) + 1 > budget:
                break
            lines.append(line)
        return "\n".join(lines) if lines else None

    @staticmethod
    def _messages_char_count(messages: list[ConversationMessage]) -> int:
        return sum(len(message.content) for message in messages)
