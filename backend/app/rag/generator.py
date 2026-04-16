import hashlib
import re

import httpx

from app.core.config import Settings
from app.models.chat import RetrievedChunk
from app.rag.prompt import SYSTEM_PROMPT, build_user_prompt


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
    ) -> str:
        provider = self.settings.llm_provider.lower()
        if provider == "template":
            return _template_answer(question, chunks, intent=intent, theme=theme)
        if provider == "ollama":
            raw = await self._ollama(
                question,
                chunks,
                intent=intent,
                theme=theme,
                avoid_verses=avoid_verses,
            )
            return _enforce_contract(raw, question=question, chunks=chunks, intent=intent, theme=theme)
        if provider == "openai":
            raw = await self._openai(
                question,
                chunks,
                intent=intent,
                theme=theme,
                avoid_verses=avoid_verses,
            )
            return _enforce_contract(raw, question=question, chunks=chunks, intent=intent, theme=theme)
        raise ValueError(f"Unknown LLM provider: {self.settings.llm_provider}")

    async def _ollama(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        *,
        intent: str,
        theme: str,
        avoid_verses: list[str],
    ) -> str:
        prompt = build_user_prompt(
            question,
            chunks,
            intent=intent,
            theme=theme,
            avoid_verses=avoid_verses,
        )
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.settings.ollama_base_url}/api/chat",
                json={
                    "model": self.settings.ollama_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0.35, "num_predict": 360, "num_ctx": 8192},
                },
            )
            response.raise_for_status()
            data = response.json()
            content = _extract_ollama_content(data)
            if content:
                return content

            # If the model returns no text due to prompt-length exhaustion, retry with a compact context.
            if data.get("done_reason") == "length":
                compact_prompt = build_user_prompt(
                    question,
                    chunks,
                    intent=intent,
                    theme=theme,
                    avoid_verses=avoid_verses,
                    max_chunks=4,
                    max_chunk_chars=220,
                )
                retry = await client.post(
                    f"{self.settings.ollama_base_url}/api/chat",
                    json={
                        "model": self.settings.ollama_model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": compact_prompt},
                        ],
                        "stream": False,
                        "think": False,
                        "options": {"temperature": 0.35, "num_predict": 320, "num_ctx": 8192},
                    },
                )
                retry.raise_for_status()
                retry_data = retry.json()
                retry_content = _extract_ollama_content(retry_data)
                if retry_content:
                    return retry_content

            return content

    async def _openai(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        *,
        intent: str,
        theme: str,
        avoid_verses: list[str],
    ) -> str:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI generation.")
        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError as exc:
            raise RuntimeError("openai package is not installed.") from exc

        client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        response = await client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0.35,
            max_tokens=360,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_user_prompt(
                        question,
                        chunks,
                        intent=intent,
                        theme=theme,
                        avoid_verses=avoid_verses,
                    ),
                },
            ],
        )
        return response.choices[0].message.content or ""


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
        "1. Direct Insight (Human Tone)\n"
        f"{insight}\n\n"
        "2. Gita Wisdom (Verse Reference + Meaning)\n"
        f"{verse}: {profile['verse_meaning']}\n"
        f"{wisdom_meaning}\n\n"
        "3. Why This Happens (Mechanism)\n"
        f"{mechanism}\n"
        f"{mechanism_tail}\n"
        "\n"
        "4. Practical Reflection (Actionable Steps)\n"
        f"- {first_step}\n"
        f"- {bullets[1]}\n"
        f"- {bullets[2]}\n"
        f"- {bullets[3]}\n\n"
        f"{punchline}"
    )
    return _post_process_answer(draft, question=question)


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
    text = answer.strip()
    if not text:
        return _template_answer(question, chunks, intent=intent, theme=theme)

    headings = [
        "1. Direct Insight (Human Tone)",
        "2. Gita Wisdom (Verse Reference + Meaning)",
        "3. Why This Happens (Mechanism)",
        "4. Practical Reflection (Actionable Steps)",
    ]

    current_index = 0
    for heading in headings:
        found = text.find(heading, current_index)
        if found == -1:
            return _template_answer(question, chunks, intent=intent, theme=theme)
        current_index = found + len(heading)

    words = len(text.replace("\n", " ").split())
    if words < 130 or words > 260:
        return _template_answer(question, chunks, intent=intent, theme=theme)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return _template_answer(question, chunks, intent=intent, theme=theme)
    if lines[-1].startswith("-") or lines[-1].startswith("*") or lines[-1].startswith("4."):
        return _template_answer(question, chunks, intent=intent, theme=theme)

    sections = _extract_sections(text)
    if sections is None:
        return _template_answer(question, chunks, intent=intent, theme=theme)

    real_life_mode = _is_real_life_query(intent=intent, theme=theme)

    if real_life_mode and not _is_theme_mechanism_valid(theme, sections["mechanism"]):
        return _template_answer(question, chunks, intent=intent, theme=theme)

    if real_life_mode and not _has_real_life_context(sections["practical"]):
        return _template_answer(question, chunks, intent=intent, theme=theme)

    if real_life_mode and not _is_theme_action_valid(theme, sections["practical"]):
        return _template_answer(question, chunks, intent=intent, theme=theme)

    section_four_start = text.find("4. Practical Reflection (Actionable Steps)")
    if section_four_start == -1:
        return _template_answer(question, chunks, intent=intent, theme=theme)
    practical_block = text[section_four_start:]
    bullet_count = sum(1 for line in practical_block.splitlines() if _is_bullet_line(line))
    if bullet_count < 3 or bullet_count > 4:
        return _template_answer(question, chunks, intent=intent, theme=theme)

    return _post_process_answer(text, question=question)


def _extract_ollama_content(payload: dict) -> str:
    message = payload.get("message", {})
    content = str(message.get("content", "") or "").strip()
    return content


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


def _post_process_answer(text: str, *, question: str) -> str:
    polished = _normalize_repetitive_context_phrase(text, question=question)
    polished = _normalize_bullets(polished)
    polished = _strip_anchor_lines(polished)
    return polished


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
        if not body:
            normalized_lines.append("-")
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
        "insight": "1. Direct Insight (Human Tone)",
        "wisdom": "2. Gita Wisdom (Verse Reference + Meaning)",
        "mechanism": "3. Why This Happens (Mechanism)",
        "practical": "4. Practical Reflection (Actionable Steps)",
    }
    try:
        i1 = text.index(headings["insight"])
        i2 = text.index(headings["wisdom"])
        i3 = text.index(headings["mechanism"])
        i4 = text.index(headings["practical"])
    except ValueError:
        return None

    if not (i1 < i2 < i3 < i4):
        return None

    return {
        "insight": text[i1 + len(headings["insight"]):i2].strip(),
        "wisdom": text[i2 + len(headings["wisdom"]):i3].strip(),
        "mechanism": text[i3 + len(headings["mechanism"]):i4].strip(),
        "practical": text[i4 + len(headings["practical"]):].strip(),
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
        clarity_loss = any(token in lowered for token in ("clarity", "confusion", "judgment", "impulse"))
        return anger_cause and anger_effect and clarity_loss
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
            token in lowered for token in ("meaning", "purpose", "empty", "hollow", "motivation")
        )
        existential_effect = any(
            token in lowered for token in ("mind", "direction", "fatigue", "paralysis", "agency")
        )
        return existential_cause and existential_effect
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
        return any(token in lowered for token in ("pause", "step away", "reframe", "time-out", "trigger", "delay"))
    if theme == "stress":
        return any(
            token in lowered for token in ("breath", "task", "deadline", "sprint", "focus", "control", "ground")
        )
    if theme == "peace":
        return any(
            token in lowered for token in ("gratitude", "comparison", "simplify", "contentment", "quiet", "wanting")
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
