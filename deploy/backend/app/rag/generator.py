import hashlib
import logging
import re
from typing import Awaitable, Callable

import httpx

from app.core.config import Settings
from app.models.chat import RetrievedChunk
from app.rag.prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


GENERIC_WELLNESS_SUBSTITUTIONS = {
    r"\bself-care\b": "disciplined care of body and mind in service of dharma",
    r"\bpractice self-compassion\b": "train the mind to become an ally through disciplined self-respect",
    r"\bbe kind to yourself\b": "do not degrade yourself; train the mind as an ally",
    r"\bexplore hobbies\b": "observe what your nature repeatedly returns to when pressure lifts",
    r"\bexplore your interests\b": "observe what your nature repeatedly returns to when pressure lifts",
    r"\btry new things\b": "test aligned duties and observe what sustains steadiness",
    r"\bbuild relationships\b": "seek sattvic association that strengthens clarity over attachment",
    r"\bset boundaries\b": "guard the gates of the senses with discernment",
    r"\bfind alternative activities\b": "redirect restless energy into one duty done with steadiness",
    r"\btake a break\b": "withdraw the senses briefly, then return to duty with steadiness",
}

GENERIC_PUNCHLINE_PHRASES = {
    "healing takes time",
    "be kind to yourself",
    "you are enough",
    "everything will be okay",
    "one step at a time",
}

PUNCHLINE_GITA_TERMS = (
    "dharma",
    "svadharma",
    "atman",
    "guna",
    "gunas",
    "sattva",
    "rajas",
    "tamas",
    "karma",
    "detachment",
    "attachment",
    "duty",
)

PROMPT_FEELING_WORDS = (
    "you are feeling",
    "you feel",
    "burnout",
    "burned out",
    "resentment",
    "overwhelmed",
    "sad",
    "lonely",
    "anxious",
    "depressed",
)

PUNCHLINE_LIBRARY = {
    "anger": [
        "Control the demand beneath anger, and the mind regains its sovereign clarity.",
        "Anger weakens when expectation loosens and action returns to disciplined purpose.",
    ],
    "stress": [
        "Pressure rules the mind only when outcomes replace duty as your center.",
        "Steadiness is won when action stays precise and outcomes lose their tyranny.",
    ],
    "grief": [
        "Loss changes form, yet the atman remains untouched by bodily ending.",
        "Grief ripens into strength when love remains, but ownership of life dissolves.",
    ],
    "focus": [
        "Attention becomes power when each return is guided by duty, not impulse.",
        "Mastery begins when the wandering mind is recalled without irritation or pride.",
    ],
    "dharma": [
        "Freedom begins when duty is chosen by nature, not borrowed from comparison.",
        "Svadharma clarifies life when imitation is dropped and responsibility is embraced.",
    ],
    "attachment": [
        "What you cling to starts commanding you; release restores intelligent action.",
        "Detachment does not reduce love; it restores freedom inside love and action.",
    ],
    "failure": [
        "Setback matures the warrior when effort stays pure and identity leaves outcomes.",
        "Results fluctuate; disciplined karma yoga keeps your direction from collapsing.",
    ],
    "default": [
        "Duty performed without ownership is the quiet architecture of unshakable freedom.",
        "When attachment loosens, discernment returns and the mind stops bargaining with reality.",
        "The mind becomes an ally when clarity governs impulse, not fear or praise.",
        "Detach from applause and blame; then your work reveals its truest power.",
    ],
}


class Generator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        *,
        intent: str,
        theme: str,
        avoid_verses: list[str],
        memory_context: str | None = None,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        provider = self.settings.llm_provider.lower()
        if provider == "template":
            answer = _template_answer(question, chunks, intent=intent, theme=theme)
            if on_token:
                for token in _stream_tokens(answer):
                    await on_token(token)
            return answer

        # Smart fallback chain: try the configured provider first, then the other, then template.
        raw = await self._generate_with_fallback(
            question,
            chunks,
            intent=intent,
            theme=theme,
            avoid_verses=avoid_verses,
            memory_context=memory_context,
            on_token=None,
            primary=provider,
        )

        final_answer = _enforce_contract(raw, question=question, chunks=chunks, intent=intent, theme=theme)
        if on_token:
            for token in _stream_tokens(final_answer):
                await on_token(token)
        return final_answer

    async def _generate_with_fallback(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        *,
        intent: str,
        theme: str,
        avoid_verses: list[str],
        memory_context: str | None,
        on_token: Callable[[str], Awaitable[None]] | None,
        primary: str,
    ) -> str:
        """Try providers in order: primary → secondary → template as last resort."""
        # Build the ordered list of providers to attempt.
        provider_order: list[str] = [primary]
        secondary = "modal" if primary == "groq" else "groq"
        provider_order.append(secondary)

        errors: list[str] = []
        for provider_name in provider_order:
            try:
                if provider_name == "groq":
                    if not self.settings.groq_api_key:
                        logger.warning("GROQ_API_KEY not configured, skipping Groq.")
                        errors.append("Groq: API key not configured")
                        continue
                    logger.info("Attempting LLM generation via Groq (%s).", self.settings.groq_model)
                    return await self._groq(
                        question, chunks,
                        intent=intent, theme=theme, avoid_verses=avoid_verses,
                        memory_context=memory_context, on_token=on_token,
                    )
                elif provider_name == "modal":
                    if not self.settings.modal_api_key:
                        logger.warning("MODAL_API_KEY not configured, skipping Modal.")
                        errors.append("Modal: API key not configured")
                        continue
                    logger.info("Attempting LLM generation via Modal (%s).", self.settings.modal_model)
                    return await self._modal(
                        question, chunks,
                        intent=intent, theme=theme, avoid_verses=avoid_verses,
                        memory_context=memory_context, on_token=on_token,
                    )
                else:
                    errors.append(f"Unknown provider: {provider_name}")
            except Exception as exc:
                logger.error("LLM provider %s failed: %s", provider_name, exc)
                errors.append(f"{provider_name}: {exc}")

        # All real providers failed — raise with diagnostic info, do NOT silently fall back to template.
        error_summary = "; ".join(errors)
        raise RuntimeError(
            f"All LLM providers failed. {error_summary}. "
            "Set GROQ_API_KEY (primary) and MODAL_API_KEY (fallback) in your environment."
        )

    async def _modal(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        *,
        intent: str,
        theme: str,
        avoid_verses: list[str],
        memory_context: str | None,
        on_token: Callable[[str], Awaitable[None]] | None,
    ) -> str:
        return await self._chat_completions_request(
            base_url=self.settings.modal_base_url,
            api_key=self.settings.modal_api_key,
            model=self.settings.modal_model,
            question=question,
            chunks=chunks,
            intent=intent,
            theme=theme,
            avoid_verses=avoid_verses,
            memory_context=memory_context,
            on_token=on_token,
        )

    async def _groq(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        *,
        intent: str,
        theme: str,
        avoid_verses: list[str],
        memory_context: str | None,
        on_token: Callable[[str], Awaitable[None]] | None,
    ) -> str:
        return await self._chat_completions_request(
            base_url=self.settings.groq_base_url,
            api_key=self.settings.groq_api_key,
            model=self.settings.groq_model,
            question=question,
            chunks=chunks,
            intent=intent,
            theme=theme,
            avoid_verses=avoid_verses,
            memory_context=memory_context,
            on_token=on_token,
        )

    async def _chat_completions_request(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        question: str,
        chunks: list[RetrievedChunk],
        intent: str,
        theme: str,
        avoid_verses: list[str],
        memory_context: str | None,
        on_token: Callable[[str], Awaitable[None]] | None,
    ) -> str:
        prompt = build_user_prompt(
            question,
            chunks,
            intent=intent,
            theme=theme,
            avoid_verses=avoid_verses,
            memory_context=memory_context,
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.35,
            "max_tokens": 420,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = _extract_chat_completions_content(data)
            if not content:
                raise RuntimeError("No assistant content returned by chat completions endpoint.")

            content = content.strip()
            if on_token:
                for token in _stream_tokens(content):
                    await on_token(token)
            return content


def _template_answer(question: str, chunks: list[RetrievedChunk], *, intent: str, theme: str) -> str:
    real_life_mode = _is_real_life_query(intent=intent, theme=theme)
    profile = _theme_profile(theme, question=question if real_life_mode else None)
    verse = _pick_verse(chunks, profile["preferred_verses"], profile["default_verse"])
    seed = _stable_index(question, f"{theme}:{intent}")
    context = _infer_real_life_context(question, theme=theme if real_life_mode else None, seed=seed + 9)

    insight = _pick_variant(profile["insights"], seed)
    wisdom_meaning = _pick_variant(profile["wisdom_meanings"], seed + 1)
    mechanism = _pick_variant(profile["mechanisms"], seed + 2)
    mechanism_tail = _pick_variant(profile["mechanism_tails"], seed + 5)
    bullets = _pick_variant(profile["action_sets"], seed + 3)
    punchline = _pick_variant(profile["punchlines"], seed + 4)
    first_step = _contextualize_step(bullets[0], context=context, seed=seed + 11) if real_life_mode else bullets[0]

    draft = (
        "Direct Insight (Human Tone)\n"
        f"{insight}\n\n"
        "Gita Wisdom (Verse Reference + Meaning)\n"
        f"{verse}: {profile['verse_meaning']}\n"
        f"{wisdom_meaning}\n\n"
        "Why This Happens (Mechanism)\n"
        f"{mechanism}\n"
        f"{mechanism_tail}\n"
        "\n"
        "Practical Reflection (Actionable Steps)\n"
        f"- {first_step}\n"
        f"- {bullets[1]}\n"
        f"- {bullets[2]}\n"
        f"- {bullets[3]}\n\n"
        "Closing Line (Punchline)\n"
        f"*{punchline}*"
    )
    return _post_process_answer(draft, question=question, theme=theme)


def _infer_real_life_context(question: str, *, theme: str | None = None, seed: int | None = None) -> str:
    lowered = question.lower()
    index_seed = seed if seed is not None else _stable_index(question, "context")

    def pick(options: list[str]) -> str:
        return options[index_seed % len(options)]

    if theme == "grief_loss":
        return pick(
            [
                "the quiet after a loved one has passed away, where their absence feels physically real",
                "days after losing someone dear, when memories come in strong waves",
                "an irreversible loss where love remains but the person is no longer physically here",
            ]
        )

    if theme == "dharma_conflict":
        return pick(
            [
                "a career choice where duty and calling do not point to the same place",
                "a family or workplace decision where approval pulls against your own nature",
                "a crossroads where the responsible path and the truest path are not identical",
            ]
        )

    if theme == "ego_conflict":
        return pick(
            [
                "a conflict where the need to win is quietly shaping the reaction",
                "a moment after comparison or criticism has made pride flare up",
                "a situation where recognition matters more than the actual work",
            ]
        )

    if theme == "attachment":
        return pick(
            [
                "a moment when the fear of losing success, love, or approval is constant",
                "a period where the mind keeps gripping an outcome as if it were identity itself",
                "a day when clinging is making even good things feel fragile",
            ]
        )

    if theme == "emotional_low":
        return pick(
            [
                "a breakup or rejection that keeps replaying in your mind at night",
                "a phase of loneliness where memories feel heavier than the present",
                "an emotional loss that makes letting go feel like losing part of yourself",
            ]
        )
    if theme == "emotional_high":
        return pick(
            [
                "a recent success that feels exciting but also hard to hold lightly",
                "a promotion or praise cycle that is quietly inflating pressure and ego",
                "a high-achievement phase where fear of losing status starts growing",
            ]
        )
    if theme == "performance_context":
        return pick(
            [
                "an exam or interview phase where preparation must outweigh worry",
                "a career stretch where consistency matters more than single outcomes",
                "a skill-building cycle that needs reflection and disciplined repetition",
            ]
        )

    if theme == "failure":
        return pick(
            [
                "the hours after a rejection when self-doubt feels louder than effort",
                "a setback where your work was real but the outcome still hurt",
                "a moment when results did not match your preparation",
            ]
        )
    if theme == "anger":
        return pick(
            [
                "a tense exchange where your tone rose before you could pause",
                "an argument where frustration replaced listening",
                "a conflict at home or work that left regret after reaction",
            ]
        )
    if theme == "stress":
        return pick(
            [
                "a deadline that is slipping while expectations keep shifting",
                "a week where urgent tasks stack faster than they clear",
                "a review cycle where goals are clear but timelines keep tightening",
            ]
        )
    if theme == "existential":
        return pick(
            [
                "a phase where daily effort feels disconnected from meaning",
                "a period of low motivation where even simple tasks feel hollow",
                "a stretch where progress exists but purpose feels distant",
            ]
        )
    if theme == "focus":
        return pick(
            [
                "a work block where attention keeps jumping to distractions",
                "a study session where your mind drifts every few minutes",
                "a task window where urgency exists but concentration does not",
            ]
        )
    if theme == "peace":
        peace_nuance = _peace_subtheme(question)
        if peace_nuance == "comparison":
            return pick(
                [
                    "scrolling through others' wins and feeling your own progress shrink",
                    "a day where someone else's success quietly became your benchmark",
                    "a phase where approval and status checks keep deciding your mood",
                ]
            )
        if peace_nuance == "restlessness":
            return pick(
                [
                    "a phase where each achievement fades quickly and the mind asks for the next one",
                    "a day that looks fine externally but still feels internally unsettled",
                    "a period where no milestone feels enough for long",
                ]
            )

    if any(token in lowered for token in ("interview", "exam", "test", "result")):
        return pick(
            [
                "a high-stakes interview where each answer feels consequential",
                "an evaluation where one uncertain answer can raise self-doubt",
                "a make-or-break conversation where the stakes feel personal",
            ]
        )
    if any(token in lowered for token in ("work", "deadline", "manager", "promotion", "career")):
        return pick(
            [
                "a deadline that is slipping while expectations keep shifting",
                "a week where urgent tasks stack faster than they clear",
                "a review cycle where goals are clear but timelines keep tightening",
            ]
        )
    if any(token in lowered for token in ("relationship", "family", "partner", "argument", "conflict")):
        return pick(
            [
                "a difficult conversation with family or your partner",
                "a tense exchange where emotions rise faster than listening",
                "a conflict where both sides feel unheard",
            ]
        )
    if any(token in lowered for token in ("failed", "failure", "rejected", "setback", "disappointed")):
        return pick(
            [
                "the hours after a rejection when self-doubt feels louder than effort",
                "a setback where your work was real but the outcome still hurt",
                "a moment when results did not match your preparation",
            ]
        )
    if any(token in lowered for token in ("meaning", "meaningless", "purpose", "empty", "motivation")):
        return pick(
            [
                "a phase where daily effort feels disconnected from meaning",
                "a period of low motivation where even simple tasks feel hollow",
                "a moment when success still feels strangely empty",
            ]
        )
    if any(token in lowered for token in ("focus", "distract", "procrast", "concentration", "wandering")):
        return pick(
            [
                "a work block where attention keeps jumping to distractions",
                "a study session where your mind drifts every few minutes",
                "a task window where urgency exists but concentration does not",
            ]
        )
    return pick(
        [
            "a situation where outcomes feel unclear and choices feel heavy",
            "days when too many possibilities pull your attention in different directions",
            "a moment when your mind jumps to worst-case outcomes before facts settle",
        ]
    )


def _enforce_contract(
    answer: str,
    *,
    question: str,
    chunks: list[RetrievedChunk],
    intent: str,
    theme: str,
) -> str:
    text = _normalize_section_headings(answer.strip())
    if not text:
        return _template_answer(question, chunks, intent=intent, theme=theme)

    headings = [
        "Direct Insight (Human Tone)",
        "Gita Wisdom (Verse Reference + Meaning)",
        "Why This Happens (Mechanism)",
        "Practical Reflection (Actionable Steps)",
        "Closing Line (Punchline)",
    ]

    current_index = 0
    for heading in headings:
        found = text.find(heading, current_index)
        if found == -1:
            return _post_process_answer(text, question=question, theme=theme)
        current_index = found + len(heading)

    words = len(text.replace("\n", " ").split())
    if words < 100 or words > 360:
        return _post_process_answer(text, question=question, theme=theme)

    if "**" in text:
        return _post_process_answer(text, question=question, theme=theme)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return _template_answer(question, chunks, intent=intent, theme=theme)
    if lines[-1].lower().startswith("closing line"):
        return _post_process_answer(text, question=question, theme=theme)

    sections = _extract_sections(text)
    if sections is None:
        return _post_process_answer(text, question=question, theme=theme)

    real_life_mode = _is_real_life_query(intent=intent, theme=theme)

    if real_life_mode and not _is_theme_mechanism_valid(theme, sections["mechanism"]):
        return _post_process_answer(text, question=question, theme=theme)

    if real_life_mode and not _has_real_life_context(sections["practical"]):
        return _post_process_answer(text, question=question, theme=theme)

    if real_life_mode and not _is_theme_action_valid(theme, sections["practical"]):
        return _post_process_answer(text, question=question, theme=theme)

    section_four_start = text.find("Practical Reflection (Actionable Steps)")
    section_five_start = text.find("Closing Line (Punchline)")
    if section_four_start == -1 or section_five_start == -1 or section_five_start <= section_four_start:
        return _post_process_answer(text, question=question, theme=theme)
    practical_block = text[section_four_start:section_five_start]
    bullet_count = sum(1 for line in practical_block.splitlines() if _is_bullet_line(line))
    if bullet_count < 3 or bullet_count > 5:
        return _post_process_answer(text, question=question, theme=theme)

    closing = sections.get("closing", "").strip()
    if not closing or "\n" in closing:
        return _post_process_answer(text, question=question, theme=theme)
    if closing.lower().startswith("closing"):
        return _post_process_answer(text, question=question, theme=theme)
    if not _is_italic_line(closing):
        return _post_process_answer(text, question=question, theme=theme)

    return _post_process_answer(text, question=question, theme=theme)


def _normalize_section_headings(text: str) -> str:
    updated = text
    patterns = [
        (
            r"^\s*[-*•#]*\s*(?:1[\).]?\s*)?direct\s+insight(?:\s*\(human\s+tone\))?\s*[:.]?\s*$",
            "Direct Insight (Human Tone)",
        ),
        (
            r"^\s*[-*•#]*\s*(?:2[\).]?\s*)?(?:gita\s+wisdom|wisdom)"
            r"(?:\s*\(verse\s+reference\s*\+\s*meaning\))?\s*[:.]?\s*$",
            "Gita Wisdom (Verse Reference + Meaning)",
        ),
        (
            r"^\s*[-*•#]*\s*(?:3[\).]?\s*)?why\s+this\s+happens(?:\s*\(mechanism\))?\s*[:.]?\s*$",
            "Why This Happens (Mechanism)",
        ),
        (
            r"^\s*[-*•#]*\s*(?:4[\).]?\s*)?practical\s+reflection"
            r"(?:\s*\(actionable\s+steps\))?\s*[:.]?\s*$",
            "Practical Reflection (Actionable Steps)",
        ),
        (
            r"^\s*[-*•#]*\s*(?:5[\).]?\s*)?closing\s+line(?:\s*\(punchline\))?\s*[:.]?\s*$",
            "Closing Line (Punchline)",
        ),
    ]

    for pattern, replacement in patterns:
        updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE | re.MULTILINE)
    return updated


def _extract_chat_completions_content(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    return str(message.get("content", "") or "")


def _stream_tokens(text: str) -> list[str]:
    words = text.split(" ")
    tokens: list[str] = []
    for index, word in enumerate(words):
        suffix = " " if index < len(words) - 1 else ""
        tokens.append(f"{word}{suffix}")
    return tokens


def _contextualize_step(step: str, *, context: str, seed: int) -> str:
    framings = [
        "In {context}, {step}",
        "When you are in {context}, {step}",
        "If you find yourself in {context}, {step}",
        "During {context}, {step}",
        "While navigating {context}, {step}",
    ]
    template = framings[seed % len(framings)]
    return template.format(context=context, step=step)


def _clean_anchor_excerpt(chunks: list[RetrievedChunk], *, max_chars: int) -> str:
    raw = chunks[0].text.split("\n", 1)[-1]
    compact = " ".join(raw.split())
    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", compact) if segment.strip()]

    for sentence in sentences:
        if len(sentence) <= max_chars:
            return sentence

    # If no clean sentence boundary fits the limit, omit anchor rather than returning a broken excerpt.
    return ""


def _post_process_answer(text: str, *, question: str, theme: str | None = None) -> str:
    polished = _normalize_section_headings(text)
    polished = _strip_malformed_asterisk_prefixes(polished)
    # Global cleanup of malformed markdown artifacts like "**." or "*."
    polished = re.sub(r'\*{1,3}\.(?:\s|$)', '', polished)
    polished = re.sub(r'^\s*\*{2,3}\s*$', '', polished, flags=re.MULTILINE)
    polished = _normalize_repetitive_context_phrase(polished, question=question)
    polished = _replace_generic_wellness_language(polished)
    polished = _correct_guna_state_mislabels(polished, question=question)
    polished = _normalize_bullets(polished)
    polished = _strip_punchline_label(polished)
    polished = _normalize_closing_line(polished)
    polished = _strip_anchor_lines(polished)
    polished = _rebuild_five_section_output(polished, question=question, theme=theme)
    return polished


def _rebuild_five_section_output(text: str, *, question: str, theme: str | None) -> str:
    sections = _extract_sections(text)
    if sections is None:
        return text

    insight = _compact_line_block(sections["insight"])
    wisdom = _normalize_wisdom_section(_compact_line_block(sections["wisdom"]), question=question)
    mechanism = _compact_line_block(sections["mechanism"])
    practical = _normalize_practical_steps(sections["practical"])
    closing = _normalize_closing_phrase(
        sections["closing"],
        previous_sections=[insight, wisdom, mechanism, practical],
        question=question,
        theme=theme,
    )

    return (
        "Direct Insight (Human Tone)\n"
        f"{insight}\n\n"
        "Gita Wisdom (Verse Reference + Meaning)\n"
        f"{wisdom}\n\n"
        "Why This Happens (Mechanism)\n"
        f"{mechanism}\n\n"
        "Practical Reflection (Actionable Steps)\n"
        f"{practical}\n\n"
        "Closing Line (Punchline)\n"
        f"{closing}"
    ).strip()


def _compact_line_block(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if not lines:
        return "Act from clarity, not from panic."
    return "\n".join(lines)


def _normalize_practical_steps(text: str) -> str:
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates: list[str] = []

    for line in raw_lines:
        if line.lower().startswith("closing line"):
            continue
        if _is_bullet_line(line):
            step = re.sub(r"^\s*(?:[-*•]|\d+\.)\s*", "", line).strip()
            if step:
                candidates.append(step)
            continue
        if line.startswith("*") and line.endswith("*"):
            continue
        # Split long plain text into sentence-like actions when bullets are missing.
        sentence_parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", line) if part.strip()]
        candidates.extend(sentence_parts if sentence_parts else [line])

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = " ".join(item.split()).strip("-• ")
        normalized = _rewrite_generic_practical_step(normalized)
        if not normalized or normalized == ".":
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(normalized)

    fallbacks = [
        "Practice indriya nigraha by withdrawing from one recurring trigger for the next day.",
        "Perform one duty as karma yoga without bargaining for immediate results.",
        "Observe the mind's guna pattern before action and choose the sattvic response.",
        "Release outcome-fixation by measuring steadiness of action, not applause or blame.",
    ]

    while len(cleaned) < 3:
        cleaned.append(fallbacks[len(cleaned)])

    cleaned = cleaned[:5]

    bullets: list[str] = []
    for item in cleaned:
        sentence = _capitalize_first_alpha(item)
        if sentence[-1] not in ".!?":
            sentence += "."
        bullets.append(f"- {sentence}")
    return "\n".join(bullets)


def _normalize_closing_phrase(
    text: str,
    *,
    previous_sections: list[str],
    question: str,
    theme: str | None,
) -> str:
    compact = " ".join(text.replace("\n", " ").split())
    candidate = _clean_punchline(compact)
    sentence = _first_sentence(candidate)

    if _should_regenerate_punchline(sentence, previous_sections):
        sentence = _generate_new_punchline(question=question, theme=theme, previous_sections=previous_sections)

    return f"*{sentence}*"


def _normalize_repetitive_context_phrase(text: str, *, question: str) -> str:
    replacements = {
        "In moments like a stressful day at work or home,": f"When {_infer_real_life_context(question)},",
        "In moments like a deadline or performance review at work,": "During a tight deadline or high-stakes review,",
        "In moments like an interview or high-stakes decision,": "When a high-pressure decision is in front of you,",
        "when your mind keeps racing": "when possibilities start to feel overwhelming",
        "uncertain stretch": "high-friction phase",
        "stressful day at work or home": "high-friction moments at work or in close relationships",
    }
    updated = text
    for old, new in replacements.items():
        updated = updated.replace(old, new)
    return updated


def _normalize_bullets(text: str) -> str:
    normalized_lines: list[str] = []
    for line in text.splitlines():
        if not _is_bullet_line(line):
            normalized_lines.append(line)
            continue

        body = re.sub(r"^\s*(?:[-*•]|\d+\.)\s*", "", line).strip()
        if not body or body in {".", "-", "*", "•"}:
            continue
        body = _capitalize_first_alpha(body)
        if body[-1] not in ".!?":
            body += "."
        normalized_lines.append(f"- {body}")
    return "\n".join(normalized_lines)


def _strip_anchor_lines(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Anchor from retrieved context:"):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _strip_punchline_label(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue
        if stripped.lower().startswith("closing punchline"):
            remainder = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            if remainder:
                cleaned_lines.append(remainder)
            continue
        if stripped.lower().startswith("closing line") and ":" in stripped:
            remainder = stripped.split(":", 1)[1].strip()
            if remainder:
                cleaned_lines.append(remainder)
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _normalize_closing_line(text: str) -> str:
    lines = text.splitlines()
    heading = "Closing Line (Punchline)"

    if heading not in text:
        trailing = ""
        for line in reversed(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if _is_bullet_line(stripped):
                continue
            if stripped in {
                "Direct Insight (Human Tone)",
                "Gita Wisdom (Verse Reference + Meaning)",
                "Why This Happens (Mechanism)",
                "Practical Reflection (Actionable Steps)",
            }:
                continue
            trailing = stripped
            break
        punchline = _clean_punchline(trailing) if trailing else "Duty performed without ownership is the quiet architecture of unshakable freedom."
        return text.rstrip() + f"\n\n{heading}\n*{punchline}*"

    if heading in lines:
        idx = lines.index(heading)
        closing_text = ""
        for i in range(idx + 1, len(lines)):
            stripped = lines[i].strip()
            if not stripped:
                continue
            closing_text = stripped
            break
    else:
        # Handle malformed inline form: "... Closing Line (Punchline) text"
        tail = text.split(heading, 1)[1].strip() if heading in text else ""
        closing_text = tail.splitlines()[0].strip() if tail else ""

    punchline = _clean_punchline(closing_text) if closing_text else "Duty performed without ownership is the quiet architecture of unshakable freedom."
    normalized_lines = [line for line in lines if line.strip() and line.strip() != heading]
    normalized_lines.append(heading)
    normalized_lines.append(f"*{punchline}*")
    return "\n".join(normalized_lines).rstrip()


def _clean_punchline(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^\*+|\*+$", "", stripped).strip()
    stripped = re.sub(r"^_+|_+$", "", stripped).strip()
    # Strip malformed marker artifacts like "**.", "*."
    stripped = re.sub(r"\*{1,3}\.\s*", "", stripped).strip()
    if stripped.lower().startswith("closing line") and ":" in stripped:
        stripped = stripped.split(":", 1)[1].strip()
    if stripped.lower().startswith("closing punchline") and ":" in stripped:
        stripped = stripped.split(":", 1)[1].strip()
    stripped = _first_sentence(stripped)
    if not stripped:
        return ""
    if stripped[-1] not in ".!?":
        stripped += "."
    # Reject truncated punchlines under 10 words
    word_count = len(re.findall(r"[A-Za-z']+", stripped))
    if word_count < 5:
        return ""
    return stripped


def _first_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return parts[0].strip()


def _replace_generic_wellness_language(text: str) -> str:
    updated = text
    for pattern, replacement in GENERIC_WELLNESS_SUBSTITUTIONS.items():
        updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)
    return updated


def _strip_malformed_asterisk_prefixes(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue

        if _is_italic_line(stripped):
            cleaned_lines.append(line)
            continue

        normalized = re.sub(r"^\s*\*{1,3}\s*[.:]\s*", "", line)
        normalized = re.sub(r"^\s*\*{2,3}\s+(?=\S)", "", normalized)
        normalized = re.sub(r"\s+\*{2,3}\s*$", "", normalized)
        if normalized.strip() in {"", ".", "*", "**", "***", "-", "•", "**.", "*."}:
            continue
        cleaned_lines.append(normalized)

    return "\n".join(cleaned_lines)


def _correct_guna_state_mislabels(text: str, *, question: str) -> str:
    lowered_question = question.lower()
    has_tamasic_signals = any(
        token in lowered_question
        for token in ("numb", "numbness", "apat", "empty", "dull", "stuck", "going through the motions")
    )

    corrected_lines: list[str] = []
    for line in text.splitlines():
        lowered_line = line.lower()
        line_has_tamasic_signals = any(
            token in lowered_line
            for token in ("numb", "numbness", "apat", "going through the motions", "inertia", "letharg", "dull")
        )
        explicit_misdiagnosis = bool(
            re.search(r"\b(this|that|your|the)\b.{0,40}\b(is|means|reflects|shows)\b.{0,20}\bsattv", lowered_line)
            or re.search(r"\bin\s+sattva\b", lowered_line)
            or re.search(r"\bstate\s+of\s+sattva\b", lowered_line)
        )
        should_correct = line_has_tamasic_signals and ("sattva" in lowered_line or "sattvic" in lowered_line)
        should_correct = should_correct or (
            has_tamasic_signals and explicit_misdiagnosis and ("sattva" in lowered_line or "sattvic" in lowered_line)
        )

        if should_correct:
            updated = re.sub(r"\bsattva\b", "tamas (often with suppressed rajas)", line, flags=re.IGNORECASE)
            updated = re.sub(r"\bsattvic\b", "tamasic", updated, flags=re.IGNORECASE)
            corrected_lines.append(updated)
            continue
        corrected_lines.append(line)
    return "\n".join(corrected_lines)


def _rewrite_generic_practical_step(step: str) -> str:
    if not step:
        return ""
    rewritten = _replace_generic_wellness_language(step).strip()
    lowered = rewritten.lower()
    if lowered in {".", "-", "*", "•"}:
        return ""

    if "self-care" in lowered or "kind to yourself" in lowered:
        return "Stabilize body and mind as instruments of dharma through disciplined routine"
    if "explore hobbies" in lowered or "explore your interests" in lowered or "try new things" in lowered:
        return "Observe what your nature repeatedly returns to when external pressure is removed"
    if "build relationships" in lowered:
        return "Choose sattvic association that strengthens clarity rather than attachment"
    return rewritten


def _normalize_wisdom_section(text: str, *, question: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return (
            "BG 2.47: You govern action, never the total field of outcomes.\n"
            f"This applies here because {_derive_problem_clause(question)}"
        )

    verse_line = next((line for line in lines if "bg" in line.lower()), lines[0])
    explanation_lines = [line for line in lines if line != verse_line]
    explanation = " ".join(explanation_lines).strip()

    if not explanation:
        explanation = f"This applies here because {_derive_problem_clause(question)}"
    elif not _is_directly_applicative(explanation):
        explanation = f"{explanation} This applies here because {_derive_problem_clause(question)}"

    explanation = _capitalize_first_alpha(explanation)
    if explanation[-1] not in ".!?":
        explanation += "."

    return f"{verse_line}\n{explanation}"


def _is_directly_applicative(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("this applies", "here because", "in your case", "because"))


def _derive_problem_clause(question: str) -> str:
    lowered = question.lower()
    if any(token in lowered for token in ("anger", "rage", "frustrat")):
        return "anger rises when expectation hardens into demand and obscures discernment."
    if any(token in lowered for token in ("stress", "pressure", "deadline", "anxious", "anxiety")):
        return "pressure intensifies when attention clings to outcomes beyond your control."
    if any(token in lowered for token in ("grief", "loss", "died", "death", "passed away")):
        return "grief deepens when love meets irreversible physical absence."
    if any(token in lowered for token in ("focus", "distract", "procrast")):
        return "attention weakens when impulses outrank disciplined return to duty."
    if any(token in lowered for token in ("compare", "jealous", "validation", "approval")):
        return "comparison converts another person's path into your measure of self-worth."
    if any(token in lowered for token in ("failure", "rejected", "setback")):
        return "setback feels existential when identity is fused with visible results."
    if any(token in lowered for token in ("dharma", "duty", "career", "purpose")):
        return "inner conflict grows when svadharma is traded for borrowed expectations."
    return "attachment and outcome-fear disturb clear action in the present moment."


def _should_regenerate_punchline(sentence: str, previous_sections: list[str]) -> bool:
    if not sentence:
        return True
    lowered = sentence.lower().strip().rstrip(".!?")
    if lowered in GENERIC_PUNCHLINE_PHRASES:
        return True
    if any(token in lowered for token in PROMPT_FEELING_WORDS):
        return True
    if not _is_gita_grounded_punchline(lowered, previous_sections):
        return True
    word_count = len(re.findall(r"[A-Za-z']+", sentence))
    if word_count < 10 or word_count > 16:
        return True
    if _punchline_repeats_previous(sentence, previous_sections):
        return True
    return False


def _punchline_repeats_previous(sentence: str, previous_sections: list[str]) -> bool:
    normalized_sentence = _normalize_compare_text(sentence)
    if not normalized_sentence:
        return True

    previous_text = " ".join(previous_sections)
    normalized_previous = _normalize_compare_text(previous_text)
    # Exact substring match
    if normalized_sentence in normalized_previous:
        return True

    sentence_words = [word for word in re.findall(r"[a-z]+", normalized_sentence) if len(word) > 2]
    if not sentence_words:
        return True

    sentence_word_set = set(sentence_words)

    # Build bigrams from punchline for phrase-level repetition detection
    sentence_bigrams = {
        f"{sentence_words[i]} {sentence_words[i + 1]}"
        for i in range(len(sentence_words) - 1)
    }

    for previous_sentence in re.split(r"(?<=[.!?])\s+", previous_text):
        prev_words = [word for word in re.findall(r"[a-z]+", previous_sentence.lower()) if len(word) > 2]
        if not prev_words:
            continue
        prev_word_set = set(prev_words)

        # Unigram overlap: 35% of punchline content words shared → reject
        overlap = len(sentence_word_set & prev_word_set)
        if overlap >= max(3, int(len(sentence_word_set) * 0.35)):
            return True

        # Bigram overlap: 3+ shared word-pairs → reject (catches paraphrasing)
        prev_bigrams = {
            f"{prev_words[i]} {prev_words[i + 1]}"
            for i in range(len(prev_words) - 1)
        }
        bigram_overlap = len(sentence_bigrams & prev_bigrams)
        if bigram_overlap >= 3:
            return True

    return False


def _is_gita_grounded_punchline(lowered_sentence: str, previous_sections: list[str]) -> bool:
    if any(term in lowered_sentence for term in PUNCHLINE_GITA_TERMS):
        return True

    combined = " ".join(previous_sections).lower()
    # If earlier sections are strongly Gita-framed, allow concise punchline without explicit jargon.
    strong_gita_context = sum(1 for term in PUNCHLINE_GITA_TERMS if term in combined) >= 3
    return strong_gita_context and any(token in lowered_sentence for token in ("clarity", "discernment", "freedom", "steadiness"))


def _normalize_compare_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9\s]", "", lowered)
    return " ".join(lowered.split())


def _generate_new_punchline(*, question: str, theme: str | None, previous_sections: list[str]) -> str:
    key = _punchline_theme_key(question=question, theme=theme)
    candidates = list(PUNCHLINE_LIBRARY.get(key, [])) + PUNCHLINE_LIBRARY["default"]
    seed = _stable_index(question, f"punchline:{key}")

    for offset in range(len(candidates)):
        candidate = candidates[(seed + offset) % len(candidates)]
        cleaned = _clean_punchline(candidate)
        if _should_regenerate_punchline(cleaned, previous_sections):
            continue
        return cleaned

    _FALLBACK_PUNCHLINES = [
        "Duty performed with detachment steadies the mind and reveals dharma with precision.",
        "Freedom is not absence of action but action freed from the tyranny of results.",
        "The warrior who sees clearly acts with force; the doubter acts with noise.",
        "Svadharma is not comfort — it is the one path your nature cannot honestly abandon.",
    ]
    fallback_seed = _stable_index(question, "punchline:fallback")
    return _FALLBACK_PUNCHLINES[fallback_seed % len(_FALLBACK_PUNCHLINES)]


def _punchline_theme_key(*, question: str, theme: str | None) -> str:
    lowered = question.lower()
    if theme in {"anger", "stress", "grief_loss", "focus", "dharma_conflict", "attachment", "failure"}:
        if theme == "grief_loss":
            return "grief"
        if theme == "dharma_conflict":
            return "dharma"
        return theme
    if any(token in lowered for token in ("anger", "rage", "frustrat")):
        return "anger"
    if any(token in lowered for token in ("stress", "pressure", "deadline", "anxiety")):
        return "stress"
    if any(token in lowered for token in ("grief", "loss", "death", "passed away")):
        return "grief"
    if any(token in lowered for token in ("focus", "distract", "procrast")):
        return "focus"
    if any(token in lowered for token in ("dharma", "duty", "calling")):
        return "dharma"
    if any(token in lowered for token in ("attach", "cling", "outcome")):
        return "attachment"
    if any(token in lowered for token in ("fail", "rejected", "setback")):
        return "failure"
    return "default"


def _is_italic_line(line: str) -> bool:
    stripped = line.strip()
    return len(stripped) >= 3 and stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**")


def _capitalize_first_alpha(text: str) -> str:
    for idx, char in enumerate(text):
        if char.isalpha():
            return text[:idx] + char.upper() + text[idx + 1 :]
    return text


def _stable_index(question: str, theme: str) -> int:
    digest = hashlib.sha256(f"{theme}::{question}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _pick_variant(options: list, seed: int):
    return options[seed % len(options)]


def _pick_verse(chunks: list[RetrievedChunk], preferred_verses: set[str], default_verse: str) -> str:
    for chunk in chunks:
        ref = f"{chunk.chapter}.{chunk.verse}"
        if ref in preferred_verses:
            return f"BG {ref}"
    return f"BG {default_verse}"


def _is_real_life_query(*, intent: str, theme: str) -> bool:
    real_life_intents = {
        "existential",
        "dharma_conflict",
        "ego_conflict",
        "attachment",
        "grief_loss",
        "emotional_low",
        "emotional_high",
        "performance_context",
        "stress",
        "anger",
        "peace",
        "failure",
        "existential",
        "focus",
    }
    real_life_themes = {
        "existential",
        "dharma_conflict",
        "ego_conflict",
        "attachment",
        "grief_loss",
        "emotional_low",
        "emotional_high",
        "performance_context",
        "stress",
        "anger",
        "peace",
        "failure",
        "existential",
        "focus",
    }
    return intent in real_life_intents or theme in real_life_themes


def _peace_subtheme(question: str) -> str:
    lowered = question.lower()
    comparison_markers = (
        "compare",
        "comparison",
        "others",
        "other people",
        "their success",
        "social media",
        "validation",
        "approval",
        "jealous",
        "behind",
    )
    restlessness_markers = (
        "restless",
        "restlessness",
        "never enough",
        "not enough",
        "unsettled",
        "uneasy",
        "keep wanting",
        "always wanting",
        "inner dissatisfaction",
        "cannot settle",
    )

    comparison_hits = sum(1 for token in comparison_markers if token in lowered)
    restlessness_hits = sum(1 for token in restlessness_markers if token in lowered)

    if comparison_hits > restlessness_hits and comparison_hits > 0:
        return "comparison"
    if restlessness_hits > comparison_hits and restlessness_hits > 0:
        return "restlessness"
    if comparison_hits > 0 and restlessness_hits > 0:
        return "mixed"
    return "neutral"


def _theme_profile(theme: str, *, question: str | None = None) -> dict:
    profiles = {
        "existential": {
            "preferred_verses": {"2.20", "2.47", "6.5", "18.66"},
            "default_verse": "2.20",
            "verse_meaning": "The deeper self is not destroyed by the body, so suffering and death do not erase meaning.",
            "anchor_fallback": "existential pain grows when suffering is treated as proof that life has no meaning",
            "insights": [
                "This question is not a detour; it is one of the Gita's centerlines.",
                "When life feels broken, the mind is asking whether value can survive suffering.",
                "The pain is real, but the conclusion that life is meaningless is not the only truth available.",
            ],
            "wisdom_meanings": [
                "The Gita answers by widening identity: what is deepest in you is not erased by pain, fear, or death.",
                "This teaching does not deny suffering; it refuses to let suffering define the totality of existence.",
                "Its invitation is to keep acting even when certainty is gone, because meaning grows through right relationship to duty.",
            ],
            "mechanisms": [
                "Existential collapse happens when pain starts speaking as if it were the final verdict on reality.",
                "The mind turns uncertainty into nihilism when it cannot yet distinguish feeling from truth.",
                "Meaning feels absent when identity is tied only to temporary outcomes.",
            ],
            "mechanism_tails": [
                "That is why the Gita responds with both ontology and action.",
                "The cure is not denial; it is a wider frame and one honest next step.",
                "When identity is steady, suffering stops claiming the whole sky.",
            ],
            "action_sets": [
                [
                    "name the question honestly instead of hiding it under distraction.",
                    "return to one duty that can be done today without needing certainty first.",
                    "sit with the thought for a minute without turning it into a verdict.",
                    "choose one small act that affirms life rather than merely analyzing it.",
                ],
                [
                    "write the question in plain words and remove the drama around it.",
                    "separate what hurts from what is true.",
                    "do one grounding act that reminds you you are still participating in life.",
                    "finish with one responsibility you can carry cleanly tonight.",
                ],
                [
                    "pause before seeking answers from noise or comparison.",
                    "hold the question as a serious one, not a shameful one.",
                    "stay with one practice that keeps you rooted in action.",
                    "let the next step be small, but unmistakably alive.",
                ],
            ],
            "punchlines": [
                "Meaning is not cancelled by suffering.",
                "A broken moment is not a broken reality.",
                "Keep acting until the horizon widens.",
            ],
        },
        "dharma_conflict": {
            "preferred_verses": {"3.35", "18.47", "2.31", "18.41"},
            "default_verse": "3.35",
            "verse_meaning": "Better to follow your own nature imperfectly than to imitate another's path perfectly.",
            "anchor_fallback": "duty confusion sharpens when borrowed expectations drown out your own nature",
            "insights": [
                "This is not just career confusion; it is a question of alignment.",
                "When duty and calling split, the mind suffers because it cannot tell obedience from integrity.",
                "Your path is not found by comparison; it is found by honest contact with your own nature.",
            ],
            "wisdom_meanings": [
                "The Gita says svadharma matters more than imitation because a borrowed path can look correct while hollowing you out.",
                "This verse is not an excuse for impulsiveness; it is a call to discern what fits your nature and responsibility.",
                "The right path is often the one that asks for courage, restraint, and long-term integrity.",
            ],
            "mechanisms": [
                "Conflict grows when external standards replace inward discernment.",
                "The mind becomes unstable when every option is measured only by social approval.",
                "Borrowed goals create inner friction because they divide effort from meaning.",
            ],
            "mechanism_tails": [
                "That is why the Gita keeps returning to duty, nature, and clear action.",
                "When the path is owned, pressure becomes simpler to bear.",
                "Clarity begins when imitation ends.",
            ],
            "action_sets": [
                [
                    "write the two competing paths and the cost of each in plain language.",
                    "separate what you truly value from what would merely impress others.",
                    "ask which choice lets you sleep with a cleaner conscience.",
                    "take one concrete step toward the path that feels truer, even if slower.",
                ],
                [
                    "identify where duty is real and where fear is speaking as duty.",
                    "compare the options against your nature, not the loudest opinion.",
                    "speak with one person who understands your work and character.",
                    "choose the next responsible action instead of waiting for perfect certainty.",
                ],
                [
                    "list what you are trying to prove and to whom.",
                    "remove any option that is only there to avoid discomfort.",
                    "look for the choice that is harder but more aligned.",
                    "treat clarity as something earned through honest action, not endless rumination.",
                ],
            ],
            "punchlines": [
                "Borrowed paths are polished, not necessarily true.",
                "Your nature is not a compromise; it is the map.",
                "Own the duty that fits your life.",
            ],
        },
        "ego_conflict": {
            "preferred_verses": {"2.47", "3.27", "12.13", "16.13"},
            "default_verse": "2.47",
            "verse_meaning": "You control the action, not the reward, so ego cannot claim ownership of the result.",
            "anchor_fallback": "ego tightens when success, comparison, or resentment becomes identity",
            "insights": [
                "The wound here is often not the event itself, but the story that your worth was challenged.",
                "Ego conflict turns a single moment into a referendum on identity.",
                "When winning becomes necessary, every setback starts feeling personal.",
            ],
            "wisdom_meanings": [
                "The Gita loosens ego by separating action from possession: you do the work, but you do not own the universe's verdict.",
                "This is how resentment loses power: identity stops depending on being above others.",
                "Humility here is not weakness; it is freedom from the need to constantly defend the self.",
            ],
            "mechanisms": [
                "Comparison narrows the mind until every other person becomes a mirror for self-worth.",
                "Resentment grows when the ego believes it was denied what it deserved.",
                "The need to win converts ordinary friction into identity threat.",
            ],
            "mechanism_tails": [
                "That is why the same event can feel small to one mind and humiliating to another.",
                "What is defended as pride often hides vulnerability.",
                "The mind gets lighter when it stops carrying its own throne.",
            ],
            "action_sets": [
                [
                    "notice the exact comparison that is triggering the heat.",
                    "separate what happened from what your ego says it means.",
                    "choose one response that is dignified instead of retaliatory.",
                    "put attention back on action, not on being seen as superior.",
                ],
                [
                    "pause before defending the self-image.",
                    "name the resentment without obeying it.",
                    "return to a concrete duty that does not need applause.",
                    "practice letting worth rest in steadiness rather than dominance.",
                ],
                [
                    "reduce the moment to facts, not status drama.",
                    "say less, observe more, and respond from clarity.",
                    "spend one minute reflecting on what part of this is about pride.",
                    "end by doing one useful action that has no audience.",
                ],
            ],
            "punchlines": [
                "The self is larger than the insult.",
                "Win the mind, and the argument shrinks.",
                "A quiet ego leaves more room for truth.",
            ],
        },
        "attachment": {
            "preferred_verses": {"2.62", "2.63", "2.70", "5.29"},
            "default_verse": "2.62",
            "verse_meaning": "Attachment narrows the mind until fear and craving disturb judgment and peace.",
            "anchor_fallback": "attachment makes the heart interpret loss as identity collapse",
            "insights": [
                "Attachment is not love itself; it is the fear that love or success is what keeps you whole.",
                "When the mind clings, even good things become sources of anxiety.",
                "What you fear losing can quietly start controlling how you live.",
            ],
            "wisdom_meanings": [
                "The Gita's detachment is not indifference; it is a way of seeing clearly without being owned by what changes.",
                "When attachment loosens, the mind can care deeply without collapsing into fear.",
                "This is where pratyahara begins in practice: the senses stop dragging the self around.",
            ],
            "mechanisms": [
                "Fear of loss creates vigilance, and vigilance makes the mind smaller.",
                "Attachment fuses identity with outcomes, so change feels like self-erasure.",
                "Craving turns ordinary uncertainty into emotional captivity.",
            ],
            "mechanism_tails": [
                "That is why even success can feel heavy when the heart cannot release it.",
                "Peace returns when caring stops becoming clinging.",
                "The tighter the grip, the less freedom remains to see clearly.",
            ],
            "action_sets": [
                [
                    "notice what you are afraid to lose and name it plainly.",
                    "separate care from clinging by returning to breath and posture.",
                    "do one small task without checking for reassurance.",
                    "practice letting one outcome remain uncertain for tonight.",
                ],
                [
                    "observe how often the mind asks for confirmation.",
                    "replace the urge to secure everything with one steady responsibility.",
                    "reduce one habit of compulsive checking or reassurance-seeking.",
                    "end the day by honoring what you value without gripping it.",
                ],
                [
                    "name the story that says you cannot be okay if this changes.",
                    "let one attachment go unanswered for a little while.",
                    "return attention to the task in front of you.",
                    "practice release as a discipline, not as a mood.",
                ],
            ],
            "punchlines": [
                "What you hold too tightly starts holding you.",
                "Care without clinging is strength.",
                "Release makes room for peace.",
            ],
        },
        "grief_loss": {
            "preferred_verses": {"2.13", "2.20"},
            "default_verse": "2.13",
            "verse_meaning": "The body changes and passes, yet the deeper self is not reduced to bodily ending.",
            "anchor_fallback": "grief carries love and final absence together, which is why it feels enduring",
            "insights": [
                "This pain carries both love and absence: someone deeply meaningful is no longer physically present.",
                "Grief after death is not just missing someone; it is learning to stand inside a reality that cannot be reversed.",
                "Your sorrow reflects the depth of bond, not a failure in how you are coping.",
            ],
            "wisdom_meanings": [
                "The Gita gently reminds that life in body is impermanent, while the deeper self is not destroyed by death.",
                "This teaching does not erase grief; it offers a wider frame so love can continue without denying loss.",
                "Its invitation is steady: honor what ended physically while holding what remains meaningful inwardly.",
            ],
            "mechanisms": [
                "Memories return intensely because the mind is trying to keep connection alive in the face of irreversible absence.",
                "Grief comes in waves since love does not end on the same timeline as physical presence.",
                "Over time, grief usually does not vanish completely; it transforms from raw shock into a different way of carrying love.",
            ],
            "mechanism_tails": [
                "That is why ordinary moments can suddenly feel heavy without warning.",
                "The goal is not quick detachment, but a gentler relationship with memory and absence.",
                "Healing is often a slow integration, not a clean endpoint.",
            ],
            "action_sets": [
                [
                    "allow the wave of grief to be felt without forcing yourself to resolve it quickly.",
                    "when memories arise, pause and breathe while naming one concrete present-moment anchor.",
                    "set aside a small daily moment to honor their memory without staying in replay all day.",
                    "choose one stabilizing routine that helps your body feel safe in the present.",
                ],
                [
                    "acknowledge softly that they are no longer physically here, and let that truth be met with compassion.",
                    "treat tears or heaviness as natural grief responses, not personal failure.",
                    "ground with one simple sensory practice when the mind spirals into replay.",
                    "end the day with one act of remembrance and one act of self-care.",
                ],
                [
                    "speak or write one memory that reflects love rather than only absence.",
                    "when pain spikes, return attention to breath, posture, and immediate surroundings.",
                    "stay connected to one trusted person so grief is not carried in isolation.",
                    "hold tomorrow gently with one realistic commitment, not a demand to feel better fast.",
                ],
            ],
            "punchlines": [
                "Grief is love learning a new form.",
                "Absence is real, and so is the bond.",
                "You do not move on from love; you carry it differently.",
            ],
        },
        "emotional_low": {
            "preferred_verses": {"2.62", "2.63", "2.70", "2.71"},
            "default_verse": "2.70",
            "verse_meaning": "When the mind is not flooded by craving and longing, it can recover inner peace.",
            "anchor_fallback": "attachment intensifies longing, so pain loops feel personal and persistent",
            "insights": [
                "This pain is not weakness; it is what attachment feels like when bond and expectation are suddenly broken.",
                "Heartbreak hurts deeply because your mind still relates to what is gone as if it were still present.",
                "In emotional loss, the mind keeps returning to memories because attachment is searching for continuity.",
            ],
            "wisdom_meanings": [
                "The Gita does not dismiss sorrow; it shows how longing settles when attachment loosens gradually.",
                "This teaching reframes pain: feelings are real, but they do not have to become your permanent identity.",
                "Its guidance is gentle and steady: let the wave pass without feeding it with repeated clinging.",
            ],
            "mechanisms": [
                "Emotionally significant memories replay because attachment marks them as essential for safety and belonging.",
                "Longing loops form when the mind keeps negotiating with reality instead of accepting the loss as real.",
                "Letting go feels like losing part of yourself because identity had fused with that relationship or hope.",
            ],
            "mechanism_tails": [
                "That is why silence and evenings can feel heavier than busy hours.",
                "The loop softens when memories are observed with compassion, not re-entered for emotional proof.",
                "Healing starts when presence becomes more trustworthy than replay.",
            ],
            "action_sets": [
                [
                    "name the feeling softly without trying to fix it in the same moment.",
                    "when memory loops start, observe the thought and return to one sensory anchor, like breath or touch.",
                    "set a gentle boundary around re-reading old messages or triggers tonight.",
                    "close the day with one grounding ritual that reconnects you to the present.",
                ],
                [
                    "allow grief space in short windows instead of suppressing it all day.",
                    "label longing as attachment pain, not as evidence that you are broken.",
                    "redirect attention to one caring action for your body and routine.",
                    "end with one line of self-kindness before sleep.",
                ],
                [
                    "acknowledge what you miss without turning it into a future story.",
                    "practice noticing thoughts as passing events, not commands.",
                    "return to present awareness whenever the mind replays old scenes.",
                    "keep tomorrow simple with one stabilizing commitment.",
                ],
            ],
            "punchlines": [
                "You are grieving a bond, not losing yourself.",
                "Let the memory pass; keep the self steady.",
                "Healing is gentle attention, repeated.",
            ],
        },
        "emotional_high": {
            "preferred_verses": {"2.48", "2.57", "2.64"},
            "default_verse": "2.48",
            "verse_meaning": "Stay balanced in success and failure by acting without clinging to outcomes.",
            "anchor_fallback": "success attachment can quietly produce ego and fear-of-loss instability",
            "insights": [
                "Success is meaningful, but attaching identity to it makes the mind fragile.",
                "Praise feels good in the moment, yet dependence on it creates hidden pressure.",
                "Highs become unstable when they are used to prove self-worth.",
            ],
            "wisdom_meanings": [
                "The Gita advises balance during success so achievement does not become ego-conditioning.",
                "This verse protects clarity: celebrate effort, but do not cling to status.",
                "Its logic is practical humility: keep duty steady while praise rises and falls.",
            ],
            "mechanisms": [
                "Success attachment creates fear of losing position, so excitement turns into vigilance.",
                "Ego builds identity around outcomes, making every future result feel existential.",
                "Validation highs train dependence on external approval, reducing inner steadiness.",
            ],
            "mechanism_tails": [
                "That is why post-success anxiety can appear even after good news.",
                "Grounded effort prevents highs from becoming future instability.",
                "Balance protects both performance and character.",
            ],
            "action_sets": [
                [
                    "acknowledge the win with gratitude, then return to your core routine.",
                    "observe pride or comparison thoughts without feeding them.",
                    "write one lesson from this success that improves process, not ego.",
                    "keep tomorrow focused on duty, not image maintenance.",
                ],
                [
                    "pause after praise and ground attention in breath for one minute.",
                    "separate your value from this single outcome.",
                    "stay humble by sharing credit where it is due.",
                    "continue consistent effort without chasing applause.",
                ],
                [
                    "enjoy the result, but avoid replaying it for validation.",
                    "notice fear-of-loss thoughts and label them as attachment.",
                    "recommit to disciplined preparation for the next responsibility.",
                    "close the day with calm gratitude instead of self-inflation.",
                ],
            ],
            "punchlines": [
                "Hold success lightly; keep effort steady.",
                "A calm win lasts longer than a loud ego.",
                "Balance protects the next step.",
            ],
        },
        "performance_context": {
            "preferred_verses": {"2.47", "2.50", "6.5"},
            "default_verse": "2.47",
            "verse_meaning": "You control effort and discipline, not final outcomes.",
            "anchor_fallback": "performance improves through disciplined inputs and detached evaluation",
            "insights": [
                "Performance grows when attention stays on controllable inputs, not imagined verdicts.",
                "One result matters less than the consistency of your method.",
                "Career and exam progress come from steady execution plus honest review.",
            ],
            "wisdom_meanings": [
                "The Gita's karma yoga model fits performance: act fully, detach from immediate result obsession.",
                "This verse keeps effort high and anxiety lower by separating duty from outcome fixation.",
                "Its method is clear: execute, review, refine, repeat.",
            ],
            "mechanisms": [
                "Result anxiety scatters focus and reduces the quality of preparation.",
                "Without structured reflection, repeated mistakes are mistaken for inability.",
                "Consistent disciplined inputs compound even when short-term outcomes vary.",
            ],
            "mechanism_tails": [
                "That is why process clarity outperforms mood-driven effort.",
                "Learning accelerates when feedback is converted into method changes.",
                "Steady action creates confidence that does not depend on one outcome.",
            ],
            "action_sets": [
                [
                    "define one measurable performance goal for this week.",
                    "break preparation into focused blocks with clear outputs.",
                    "after each session, note one mistake and one specific adjustment.",
                    "track consistency daily instead of checking final results repeatedly.",
                ],
                [
                    "start with the highest-impact task before low-value activity.",
                    "use timed practice and review error patterns objectively.",
                    "revise strategy where evidence shows weakness.",
                    "close with one deliberate next step for tomorrow.",
                ],
                [
                    "separate what is controllable today from what is not.",
                    "practice under realistic constraints to build reliability.",
                    "convert feedback into one concrete process change.",
                    "sustain effort rhythm regardless of yesterday's outcome.",
                ],
            ],
            "punchlines": [
                "Discipline compounds when results fluctuate.",
                "Method first, outcome next.",
                "Consistency is performance in slow motion.",
            ],
        },
        "anger": {
            "preferred_verses": {"2.62", "2.63"},
            "default_verse": "2.62",
            "verse_meaning": "Fixation becomes attachment, attachment becomes craving, and blocked craving erupts as anger.",
            "anchor_fallback": "when craving hardens into demand, frustration escalates quickly",
            "insights": [
                "Your anger is often a signal that reality broke an expectation you were gripping tightly.",
                "The strongest anger usually starts as a silent demand: this must go my way.",
                "What feels like sudden rage is often a buildup of attachment and unmet expectation.",
            ],
            "wisdom_meanings": [
                "The Gita maps anger as a sequence, not a personality flaw, which means it can be interrupted.",
                "This verse treats anger as a chain reaction, so the key is to break the chain early.",
                "The teaching is practical: catch attachment before it hardens into demand.",
            ],
            "mechanisms": [
                "Attachment narrows attention around one desired outcome; when blocked, the mind shifts into threat mode.",
                "Craving turns preference into entitlement, and entitlement converts disappointment into heat.",
                "When expectation becomes identity, resistance feels personal, and anger spikes fast.",
            ],
            "mechanism_tails": [
                "Clarity drops first, so reaction takes the wheel unless you interrupt the loop.",
                "Once this loop starts, your body speaks before your values do.",
                "If unbroken, this chain turns a momentary trigger into a prolonged conflict.",
            ],
            "action_sets": [
                [
                    "pause for ten seconds before speaking.",
                    "Step away briefly to lower body tension before returning.",
                    "Reframe the thought from 'must' to 'preferred but not required'.",
                    "State one clear request instead of replaying the offense.",
                ],
                [
                    "slow your breathing and relax your jaw before responding.",
                    "Delay the hard conversation until your tone is steady.",
                    "Name the unmet expectation in plain words.",
                    "Choose one constructive next move, not a retaliatory one.",
                ],
                [
                    "label the trigger: expectation, disrespect, or fear.",
                    "Use a short time-out rather than arguing while flooded.",
                    "Ask 'what outcome do I want in 24 hours?' before reacting.",
                    "Return with one boundary and one practical ask.",
                ],
            ],
            "punchlines": [
                "Anger is expectation that reality refused.",
                "Catch the demand early, and the fire stays small.",
                "When expectation loosens, anger loses fuel.",
            ],
        },
        "stress": {
            "preferred_verses": {"2.14", "2.56"},
            "default_verse": "2.56",
            "verse_meaning": "Steadiness comes from tolerating changing highs and lows without losing inner balance.",
            "anchor_fallback": "stability grows by returning attention to what is in your control",
            "insights": [
                "Pressure feels crushing when your mind tries to solve outcome and task at the same time.",
                "Calm is not the absence of pressure; it is skill under pressure.",
                "When uncertainty rises, clarity comes from narrowing to the next controllable step.",
            ],
            "wisdom_meanings": [
                "The Gita teaches endurance of dualities, so stress is handled through stability, not escape.",
                "This verse reframes pressure as temporary waves, not permanent identity.",
                "Its message is practical: regulate the mind first, then execute the duty.",
            ],
            "mechanisms": [
                "Under pressure, the mind predicts worst-case futures and drains attention from present action.",
                "When discomfort is treated as danger, your body escalates and decision quality drops.",
                "Duality reactivity pulls you between fear and urgency; steadiness restores judgment.",
            ],
            "mechanism_tails": [
                "That is how overwhelm grows: attention scatters, then errors rise.",
                "Without grounding, uncertainty gets mistaken for incapability.",
                "Regulation first, execution second, is what preserves performance.",
            ],
            "action_sets": [
                [
                    "take three slow breaths before the next decision.",
                    "Split a large deadline into one 20-minute action block.",
                    "Focus on execution quality, not imagined outcomes.",
                    "After each block, reset posture and attention for 30 seconds.",
                ],
                [
                    "ground yourself by exhaling longer than you inhale.",
                    "Write the single next task that moves the situation forward.",
                    "Treat urgency as a signal to simplify, not to rush.",
                    "Use short review checkpoints instead of constant self-judgment.",
                ],
                [
                    "name what is controllable in this hour.",
                    "work in focused sprints rather than panic multitasking.",
                    "replace catastrophic thoughts with task-specific language.",
                    "close the day by noting one stable response you kept.",
                ],
            ],
            "punchlines": [
                "Stability is trained before the storm.",
                "Pressure shrinks when attention gets specific.",
                "Steadiness is a skill, not a mood.",
            ],
        },
        "peace": {
            "preferred_verses": {"2.71", "5.29"},
            "default_verse": "2.71",
            "verse_meaning": "Peace grows when craving and ego-ownership loosen, and life is met with sufficiency.",
            "anchor_fallback": "peace strengthens as comparison and grasping are reduced",
            "insights": [
                "Inner peace is usually blocked less by events and more by constant inner chasing.",
                "Restlessness often means the mind is bargaining with life for 'one more' condition.",
                "Peace starts when you stop measuring your worth against every external result.",
            ],
            "wisdom_meanings": [
                "The verse links peace to letting go of possessiveness, not to passive withdrawal.",
                "Its point is direct: release craving and egoic ownership, and mental friction decreases.",
                "This is not apathy; it is freedom from compulsive grasping.",
            ],
            "mechanisms": [
                "Craving creates a moving target, so satisfaction keeps getting postponed.",
                "Ego-ownership turns every outcome into self-worth, which sustains inner agitation.",
                "When wanting slows and comparison drops, the nervous system exits constant scarcity mode.",
            ],
            "mechanism_tails": [
                "This is why external wins can still feel internally noisy.",
                "Peace returns when identity is no longer tied to endless acquisition.",
                "Less inner bargaining means more mental quiet in ordinary moments.",
            ],
            "action_sets": [
                [
                    "start the morning by naming three things already sufficient today.",
                    "reduce one comparison trigger, such as unnecessary social scrolling.",
                    "practice one task daily with full attention and no performance story.",
                    "end the day with a short gratitude note instead of outcome tallying.",
                ],
                [
                    "pause when you notice 'I'll be okay when...' thinking.",
                    "simplify one desire this week into a non-essential preference.",
                    "replace comparison with contribution: what can I give right now?",
                    "set one boundary that protects mental quiet in evenings.",
                ],
                [
                    "notice where ego says 'mine' and soften that grip.",
                    "choose fewer inputs to reduce mental noise during the day.",
                    "practice contentment in one ordinary moment, like a meal or walk.",
                    "close conflicts with understanding, not score-keeping.",
                ],
            ],
            "punchlines": [
                "Peace begins when wanting slows down.",
                "Less chasing, more clarity.",
                "When comparison fades, quiet returns.",
            ],
        },
        "failure": {
            "preferred_verses": {"2.47", "2.38"},
            "default_verse": "2.47",
            "verse_meaning": "You are responsible for effort, not entitled to outcomes; stay steady in success and failure.",
            "anchor_fallback": "effort remains meaningful even when results delay",
            "insights": [
                "Failure hurts most when you confuse one outcome with your whole worth.",
                "Setbacks feel personal, but they are often feedback on process, not identity.",
                "Rejection can shake confidence, yet it can also clarify how to train next.",
            ],
            "wisdom_meanings": [
                "The Gita separates action from result-identity, which protects dignity after loss.",
                "This teaching does not deny pain; it prevents pain from defining the self.",
                "Its logic is practical: keep duty stable even when results fluctuate.",
            ],
            "mechanisms": [
                "When outcome becomes identity, rejection feels like personal invalidation rather than one event.",
                "Result-attachment amplifies disappointment into helplessness and withdrawal.",
                "A single setback can dominate memory when effort and worth are fused together.",
            ],
            "mechanism_tails": [
                "That fusion is what turns temporary pain into long-lasting self-doubt.",
                "Separating effort from ego restores agency after disappointment.",
                "Steady action reopens momentum faster than self-judgment loops.",
            ],
            "action_sets": [
                [
                    "write three concrete efforts you did well before reviewing the result.",
                    "extract one process lesson and apply it in the next attempt.",
                    "set a short recovery window, then restart with a smaller target.",
                    "share the setback with one trusted person to prevent isolation.",
                ],
                [
                    "name the loss honestly without turning it into an identity statement.",
                    "rebuild momentum with one task you can complete today.",
                    "track inputs you control rather than obsessing over verdicts.",
                    "close the day by noting one improvement from this setback.",
                ],
                [
                    "replace 'i failed' with 'this attempt failed'.",
                    "revise your method in one measurable way for the next round.",
                    "protect sleep and routine so disappointment does not spiral.",
                    "commit to one next attempt date before the day ends.",
                ],
            ],
            "punchlines": [
                "Results fluctuate; disciplined effort compounds.",
                "Setback is information, not identity.",
                "Your worth is not a scoreboard.",
            ],
        },
        "existential": {
            "preferred_verses": {"6.5", "18.66"},
            "default_verse": "6.5",
            "verse_meaning": "Lift yourself by your own mind; do not let your mind become your enemy.",
            "anchor_fallback": "meaning returns through aligned responsibility and inner steadiness",
            "insights": [
                "Meaning often fades when life becomes motion without inner direction.",
                "Emptiness is not proof that life is pointless; it is a signal to realign.",
                "Low motivation can reflect disconnection from values, not lack of ability.",
            ],
            "wisdom_meanings": [
                "The Gita points to self-upliftment: your mind can be trained into an ally.",
                "This verse emphasizes agency, even when motivation feels absent.",
                "Its guidance is grounding: return to purpose through disciplined inner leadership.",
            ],
            "mechanisms": [
                "When action loses connection to meaning, effort feels hollow and motivation collapses.",
                "An untrained mind loops on emptiness narratives and blocks forward movement.",
                "Purpose erosion turns small uncertainty into broad existential fatigue.",
            ],
            "mechanism_tails": [
                "Rebuilding meaning starts with one aligned responsibility, not a grand revelation.",
                "Structure and surrender reduce mental paralysis faster than overthinking purpose.",
                "Inner guidance strengthens when attention shifts from rumination to serviceful action.",
            ],
            "action_sets": [
                [
                    "choose one value you still respect and act on it for 20 minutes today.",
                    "limit late-night rumination by setting a fixed sleep boundary.",
                    "create a daily meaning ritual, such as reflection, prayer, or journaling.",
                    "help one person in a small way to reconnect effort with contribution.",
                ],
                [
                    "write one sentence on why your current duty still matters.",
                    "reduce mental noise by cutting one draining input source this week.",
                    "anchor your morning with a grounding practice before screens.",
                    "end the day noting one action that felt aligned, not just productive.",
                ],
                [
                    "start with one responsibility that reflects your deeper values.",
                    "treat emptiness as a signal to simplify, not to self-condemn.",
                    "schedule one conversation with someone who gives perspective.",
                    "repeat one grounding line when nihilistic thoughts spike.",
                ],
            ],
            "punchlines": [
                "Meaning grows where responsibility is lived.",
                "Direction returns one aligned step at a time.",
                "A trained mind rebuilds purpose.",
            ],
        },
        "focus": {
            "preferred_verses": {"6.26"},
            "default_verse": "6.26",
            "verse_meaning": "Whenever the mind wanders, bring it back under steady guidance.",
            "anchor_fallback": "focus strengthens through repeated redirection rather than force",
            "insights": [
                "Focus is less about intensity and more about repeated return.",
                "Distraction often wins when tasks are vague and attention has no anchor.",
                "A wandering mind is normal; training begins in how quickly you return.",
            ],
            "wisdom_meanings": [
                "The Gita treats concentration as a practice of redirection, not suppression.",
                "This verse normalizes distraction and prescribes disciplined return.",
                "Its method is concrete: notice drift, then restore attention deliberately.",
            ],
            "mechanisms": [
                "Attention fragments when cues and impulses outrank your chosen priority.",
                "Without deliberate return, mind wandering becomes the default loop.",
                "Task-switching rewards novelty and weakens sustained cognitive control.",
            ],
            "mechanism_tails": [
                "Focus improves when return cycles outnumber distraction cycles.",
                "Clarity rises once one task holds attention long enough to gain depth.",
                "Discipline is built through repeated correction, not perfect concentration.",
            ],
            "action_sets": [
                [
                    "define one clear task and a 25-minute focus block before starting.",
                    "silence nonessential notifications during deep work windows.",
                    "when you drift, write the distraction and return immediately.",
                    "finish with a 2-minute review of what sustained your attention.",
                ],
                [
                    "start work with the hardest cognitive task before easy admin tasks.",
                    "use a visible timer to reduce unconscious task switching.",
                    "keep a distraction pad so thoughts are captured, not chased.",
                    "take short deliberate breaks instead of random scrolling.",
                ],
                [
                    "set one outcome for this session and ignore side quests.",
                    "batch similar tasks so attention does not reset repeatedly.",
                    "use a reset breath whenever the mind jumps away.",
                    "end the block by pre-writing the first step for the next block.",
                ],
            ],
            "punchlines": [
                "Focus is built in the return, not the start.",
                "Attention grows where redirection is consistent.",
                "Discipline is repeated return.",
            ],
        },
        "general": {
            "preferred_verses": set(),
            "default_verse": "2.47",
            "verse_meaning": "Clarity comes from doing the next right action without clinging to outcomes.",
            "anchor_fallback": "clarity improves when action is separated from outcome obsession",
            "insights": [
                "You move better when you separate what you can do from what you cannot control.",
                "Most confusion reduces when you return to one clear duty at a time.",
                "When the mind stops bargaining with outcomes, decisions become cleaner.",
            ],
            "wisdom_meanings": [
                "The Gita keeps returning to disciplined action as the anchor for mental balance.",
                "Its guidance is practical: commit to process, then release over-attachment to result.",
                "The teaching protects energy by moving attention from fantasy to responsibility.",
            ],
            "mechanisms": [
                "Outcome-clinging splits attention between imagined futures and present tasks.",
                "That split creates anxiety loops and weakens execution quality.",
                "Process focus restores agency and reduces emotional volatility.",
            ],
            "mechanism_tails": [
                "This shift replaces rumination with useful momentum.",
                "Mental load decreases when the next action is concrete.",
                "Agency grows when attention stops leaking into prediction loops.",
            ],
            "action_sets": [
                [
                    "define one concrete task for the next 25 minutes.",
                    "replace 'what if' thinking with 'what now' planning.",
                    "finish one meaningful step before checking results.",
                    "review your response quality, not just the outcome.",
                ],
                [
                    "list what is controllable in this situation.",
                    "act on the smallest high-value next step.",
                    "set a short time window for focused execution.",
                    "end with one lesson, one improvement, one release.",
                ],
                [
                    "pause before reacting to uncertainty.",
                    "translate stress into one immediate responsibility.",
                    "keep language specific: task, deadline, next move.",
                    "note one way you stayed grounded today.",
                ],
            ],
            "punchlines": [
                "Clarity follows committed action.",
                "Do the next right step, then release the rest.",
                "Steady process beats noisy prediction.",
            ],
        },
    }
    base = profiles.get(theme, profiles["general"])

    if theme != "peace" or not question:
        return base

    peace_nuance = _peace_subtheme(question)
    if peace_nuance in {"mixed", "neutral"}:
        return base

    if peace_nuance == "comparison":
        return {
            **base,
            "anchor_fallback": "social comparison converts self-worth into a moving external benchmark",
            "insights": [
                "Comparison exhausts you because your standard keeps moving with other people, not your values.",
                "You can be progressing and still feel behind when others become your mirror.",
                "External validation feels urgent, but it rarely gives lasting peace.",
            ],
            "mechanisms": [
                "Social comparison turns identity into a public scoreboard that never stabilizes.",
                "When worth is outsourced to others' progress, your nervous system stays in threat and deficiency mode.",
                "External validation loops keep attention outward, which blocks inner sufficiency.",
            ],
            "mechanism_tails": [
                "That is why even good days feel small after one comparison trigger.",
                "Peace returns when values, not rankings, become the reference point.",
                "Attention shifts from envy to direction when self-worth leaves the scoreboard.",
            ],
            "action_sets": [
                [
                    "reduce one social comparison trigger, especially reactive scrolling windows.",
                    "name one value-based metric for today that does not depend on others.",
                    "replace status checking with one concrete contribution task.",
                    "end the day by tracking your own progress delta, not someone else's highlight.",
                ],
                [
                    "pause the moment someone else's success changes your mood.",
                    "ask what standard you actually believe in before reacting.",
                    "limit validation-seeking behaviors for one focused block.",
                    "re-center on one action that matches your long-term direction.",
                ],
                [
                    "notice when admiration turns into self-judgment.",
                    "turn comparison into learning by extracting one useful practice.",
                    "stop checking rankings during high-friction parts of the day.",
                    "close with one sentence of self-respect tied to effort.",
                ],
            ],
            "punchlines": [
                "Peace grows when your yardstick is yours.",
                "A borrowed benchmark steals quiet.",
                "Direction beats comparison.",
            ],
        }

    return {
        **base,
        "anchor_fallback": "inner restlessness is fueled by endless condition-setting and wanting",
        "insights": [
            "Restlessness often continues even without comparison, because the mind keeps negotiating for one more condition.",
            "Inner dissatisfaction grows when arrival is always postponed to the next milestone.",
            "The problem is not lack of achievement, but lack of inner completion between achievements.",
        ],
        "mechanisms": [
            "Constant wanting trains the brain to scan for what is missing rather than what is sufficient.",
            "Conditioned satisfaction delays peace into the future, so the present never feels enough.",
            "When desire keeps resetting the baseline, calm cannot consolidate.",
        ],
        "mechanism_tails": [
            "That is why emptiness can persist even after visible progress.",
            "Peace becomes possible when wanting is held as preference, not requirement.",
            "The mind quiets when sufficiency is practiced in ordinary moments.",
        ],
        "action_sets": [
            [
                "pause when you notice 'I'll be okay when...' thoughts and label them as conditional peace.",
                "simplify one active desire into a preference for this week.",
                "practice one routine activity slowly to train sufficiency in the present.",
                "close the day with three 'already enough' observations.",
            ],
            [
                "identify one recurring 'next condition' your mind keeps chasing.",
                "set a short no-optimization window to rest the improvement loop.",
                "replace urgency to upgrade with one act of contented attention.",
                "end with one gratitude line tied to today, not future outcomes.",
            ],
            [
                "notice where wanting quietly drives your mood.",
                "practice finishing one task without immediately chasing the next.",
                "create an evening boundary that protects quiet from endless inputs.",
                "mark one ordinary moment as complete before sleep.",
            ],
        ],
        "punchlines": [
            "Peace starts when 'next' stops running your mind.",
            "Enough is practiced, not purchased.",
            "Quiet grows when wanting loosens.",
        ],
    }


def _extract_sections(text: str) -> dict[str, str] | None:
    headings = {
        "insight": "Direct Insight (Human Tone)",
        "wisdom": "Gita Wisdom (Verse Reference + Meaning)",
        "mechanism": "Why This Happens (Mechanism)",
        "practical": "Practical Reflection (Actionable Steps)",
        "closing": "Closing Line (Punchline)",
    }
    try:
        i1 = text.index(headings["insight"])
        i2 = text.index(headings["wisdom"])
        i3 = text.index(headings["mechanism"])
        i4 = text.index(headings["practical"])
        i5 = text.index(headings["closing"])
    except ValueError:
        return None

    if not (i1 < i2 < i3 < i4 < i5):
        return None

    return {
        "insight": text[i1 + len(headings["insight"]):i2].strip(),
        "wisdom": text[i2 + len(headings["wisdom"]):i3].strip(),
        "mechanism": text[i3 + len(headings["mechanism"]):i4].strip(),
        "practical": text[i4 + len(headings["practical"]):i5].strip(),
        "closing": text[i5 + len(headings["closing"]):].strip(),
    }


def _is_theme_mechanism_valid(theme: str, mechanism: str) -> bool:
    lowered = mechanism.lower()
    if theme == "grief_loss":
        grief_cause = any(
            token in lowered
            for token in ("death", "absence", "irreversible", "memory", "memories", "loss", "physically")
        )
        grief_effect = any(
            token in lowered
            for token in ("love", "waves", "grief", "carry", "integration", "healing", "transform")
        )
        return grief_cause and grief_effect
    if theme == "emotional_low":
        low_cause = any(
            token in lowered for token in ("attachment", "longing", "memory", "replay", "separation", "loss")
        )
        low_effect = any(
            token in lowered for token in ("pain", "grief", "loop", "self", "healing", "identity")
        )
        return low_cause and low_effect
    if theme == "emotional_high":
        high_cause = any(
            token in lowered for token in ("success", "praise", "ego", "validation", "outcome", "pride")
        )
        high_effect = any(
            token in lowered for token in ("fear", "loss", "instability", "pressure", "balance", "identity")
        )
        return high_cause and high_effect
    if theme == "performance_context":
        perf_cause = any(
            token in lowered for token in ("result", "exam", "career", "feedback", "preparation", "anxiety")
        )
        perf_effect = any(
            token in lowered for token in ("focus", "method", "learning", "discipline", "consistency")
        )
        return perf_cause and perf_effect
    if theme == "anger":
        anger_cause = any(token in lowered for token in ("attachment", "desire", "craving", "expectation"))
        anger_effect = any(token in lowered for token in ("anger", "frustration", "rage", "react"))
        return anger_cause and anger_effect
    if theme == "stress":
        stress_inputs = any(
            token in lowered for token in ("pressure", "uncertainty", "duality", "overload", "stress")
        )
        stress_regulation = any(
            token in lowered for token in ("steady", "stability", "regulate", "ground", "focus", "judgment")
        )
        return stress_inputs and stress_regulation
    if theme == "peace":
        peace_cause = any(token in lowered for token in ("desire", "craving", "ego", "comparison", "wanting"))
        peace_effect = any(token in lowered for token in ("peace", "agitation", "quiet", "content", "restless"))
        return peace_cause and peace_effect
    if theme == "failure":
        failure_cause = any(
            token in lowered for token in ("result", "outcome", "rejection", "setback", "failure")
        )
        failure_effect = any(
            token in lowered for token in ("identity", "self-doubt", "helpless", "withdrawal", "worth")
        )
        return failure_cause and failure_effect
    if theme == "existential":
        existential_cause = any(
            token in lowered for token in ("meaning", "purpose", "empty", "hollow", "motivation", "suffering", "death")
        )
        existential_effect = any(
            token in lowered for token in ("mind", "direction", "fatigue", "paralysis", "agency")
        )
        return existential_cause and existential_effect
    if theme == "dharma_conflict":
        dharma_cause = any(
            token in lowered for token in ("duty", "calling", "career", "path", "choice", "svadharma", "moral")
        )
        dharma_effect = any(
            token in lowered for token in ("clarity", "integrity", "alignment", "pressure", "conflict", "nature")
        )
        return dharma_cause and dharma_effect
    if theme == "ego_conflict":
        ego_cause = any(
            token in lowered for token in ("ego", "pride", "comparison", "win", "winning", "validation", "recognition")
        )
        ego_effect = any(
            token in lowered for token in ("humility", "resentment", "identity", "heat", "conflict", "self")
        )
        return ego_cause and ego_effect
    if theme == "attachment":
        attachment_cause = any(
            token in lowered for token in ("attachment", "attached", "cling", "fear", "losing", "approval", "outcome")
        )
        attachment_effect = any(
            token in lowered for token in ("peace", "restless", "identity", "control", "loss", "clinging")
        )
        return attachment_cause and attachment_effect
    if theme == "focus":
        focus_cause = any(
            token in lowered for token in ("attention", "distraction", "wandering", "task-switch", "fragment")
        )
        focus_effect = any(
            token in lowered for token in ("return", "discipline", "concentration", "control", "focus")
        )
        return focus_cause and focus_effect
    return True


def _has_real_life_context(practical: str) -> bool:
    lowered = practical.lower()
    markers = (
        "work",
        "deadline",
        "interview",
        "decision",
        "relationship",
        "family",
        "conversation",
        "meeting",
        "home",
        "rejection",
        "setback",
        "review",
        "choices",
        "study",
        "heartbreak",
        "lonely",
        "grief",
        "death",
        "died",
        "passed away",
        "gone",
        "absence",
        "funeral",
        "breakup",
        "promotion",
        "praise",
        "career",
        "exam",
        "interview",
        "friend",
        "betray",
        "betrayal",
        "revenge",
        "trust",
    )
    return any(marker in lowered for marker in markers)


def _is_theme_action_valid(theme: str, practical: str) -> bool:
    lowered = practical.lower()
    if theme == "grief_loss":
        return any(
            token in lowered
            for token in ("breathe", "anchor", "memory", "honor", "present", "compassion", "routine", "trusted")
        )
    if theme == "emotional_low":
        return any(
            token in lowered
            for token in ("accept", "observe", "ground", "present", "breath", "gentle", "self-kind")
        )
    if theme == "emotional_high":
        return any(
            token in lowered
            for token in ("ground", "humble", "gratitude", "observe ego", "steady", "duty", "credit")
        )
    if theme == "performance_context":
        return any(
            token in lowered
            for token in ("strategy", "review", "practice", "consistency", "method", "feedback", "goal")
        )
    if theme == "anger":
        return any(
            token in lowered
            for token in (
                "pause",
                "step away",
                "reframe",
                "time-out",
                "trigger",
                "delay",
                "acknowledge",
                "self-reflection",
                "seek support",
                "temporary",
            )
        )
    if theme == "stress":
        return any(
            token in lowered for token in ("breath", "task", "deadline", "sprint", "focus", "control", "ground")
        )
    if theme == "peace":
        return any(
            token in lowered for token in ("gratitude", "comparison", "simplify", "contentment", "quiet", "wanting")
        )
    if theme == "dharma_conflict":
        return any(
            token in lowered for token in ("clarity", "choose", "journal", "align", "reflect", "responsibility", "svadharma")
        )
    if theme == "ego_conflict":
        return any(
            token in lowered for token in ("observe", "pause", "humble", "reframe", "compassion", "steady", "detach")
        )
    if theme == "attachment":
        return any(
            token in lowered for token in ("release", "steady", "breathe", "observe", "withdraw", "non-attachment", "care")
        )
    if theme == "failure":
        return any(
            token in lowered
            for token in ("lesson", "next attempt", "recovery", "inputs", "effort", "setback", "restart")
        )
    if theme == "existential":
        return any(
            token in lowered
            for token in ("value", "meaning", "ground", "ritual", "responsibility", "contribution", "aligned")
        )
    if theme == "focus":
        return any(
            token in lowered
            for token in ("focus block", "timer", "distraction", "return", "deep work", "task", "attention")
        )
    return True


def _is_bullet_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("-") or stripped.startswith("*") or stripped.startswith("•"):
        return True
    if re.match(r"^\d+\.\s", stripped):
        section_titles = (
            "1. Direct Insight (Human Tone)",
            "2. Gita Wisdom (Verse Reference + Meaning)",
            "3. Why This Happens (Mechanism)",
            "4. Practical Reflection (Actionable Steps)",
        )
        return stripped not in section_titles
    return False
