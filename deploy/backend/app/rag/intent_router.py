import math
from dataclasses import dataclass

from app.rag.embeddings import EmbeddingProvider


@dataclass(frozen=True)
class IntentRoute:
    intent: str
    confidence: float
    matched_keywords: list[str]


INTENT_DEFINITIONS = {
    "existential": {
        "keywords": [
            "meaning",
            "meaning of life",
            "purpose of life",
            "life matter",
            "does my life matter",
            "why live",
            "why is the world broken",
            "world broken",
            "broken world",
            "suffering",
            "injustice",
            "death",
            "existence",
            "existential",
        ],
        "prototype": "existential questions about suffering, purpose, death, brokenness, and whether life matters",
    },
    "dharma_conflict": {
        "keywords": [
            "dharma",
            "svadharma",
            "calling",
            "career or calling",
            "duty",
            "moral conflict",
            "should i quit",
            "should i stay",
            "right path",
            "my path",
            "imposter",
            "family pressure",
            "what should i do",
        ],
        "prototype": "duty versus calling, moral conflict, and learning to follow one's own path without imitation",
    },
    "ego_conflict": {
        "keywords": [
            "winning",
            "prove them wrong",
            "resentment",
            "resentful",
            "humiliated",
            "pride",
            "ego",
            "validation",
            "recognized",
            "recognition",
            "envy",
            "jealous",
            "comparison",
        ],
        "prototype": "ego-driven conflict, resentment, comparison, and the urge to defend identity through victory",
    },
    "attachment": {
        "keywords": [
            "fear of losing",
            "can't let go",
            "cannot let go",
            "cling",
            "clinging",
            "attached",
            "attachment",
            "afraid to lose",
            "dependent",
            "hold on",
            "need approval",
            "success",
            "outcome",
        ],
        "prototype": "attachment to outcomes, success, approval, and identity becoming fused with what may be lost",
    },
    "grief_loss": {
        "keywords": [
            "death",
            "died",
            "passed away",
            "passed on",
            "they are gone",
            "gone forever",
            "no longer here",
            "lost my",
            "funeral",
        ],
        "prototype": "irreversible grief after death of a loved one, with finality, absence, and recurring memories",
    },
    "emotional_low": {
        "keywords": [
            "heartbreak",
            "love failure",
            "lonely",
            "loneliness",
            "grief",
            "loss",
            "unwanted",
            "miss",
            "separation",
            "memories",
            "replaying memories",
        ],
        "prototype": "emotional pain, heartbreak, rejection, grief, and attachment-driven longing",
    },
    "emotional_high": {
        "keywords": [
            "success",
            "achievement",
            "praise",
            "promotion",
            "hike",
            "excited",
            "overconfident",
            "proud",
            "ego",
            "validation",
        ],
        "prototype": "success highs, praise, pride, and attachment to outcomes that destabilize balance",
    },
    "performance_context": {
        "keywords": [
            "exam",
            "interview",
            "career",
            "job",
            "result",
            "productivity",
            "practice",
            "skill",
            "improve",
            "performance",
        ],
        "prototype": "performance situations in study or career requiring disciplined action and learning",
    },
    "stress": {
        "keywords": [
            "stress",
            "pressure",
            "deadline",
            "anxiety",
            "anxious",
            "panic",
            "overwhelmed",
            "urgent",
            "tension",
        ],
        "prototype": "pressure, deadlines, anxiety, and emotional overload under uncertainty",
    },
    "anger": {
        "keywords": [
            "anger",
            "angry",
            "yell",
            "yelled",
            "shout",
            "shouted",
            "frustration",
            "frustrated",
            "rage",
            "resentment",
            "snap",
            "snapped",
            "argument",
            "fight",
            "conflict",
            "regret after anger",
            "regret yelling",
            "irritated",
            "triggered",
        ],
        "prototype": "conflict, frustration, reactive anger, and regret after emotional outburst",
    },
    "peace": {
        "keywords": [
            "peace",
            "inner peace",
            "restless",
            "dissatisfied",
            "comparison",
            "jealous",
            "contentment",
            "never enough",
        ],
        "prototype": "restlessness, dissatisfaction, comparison, and inability to feel content",
    },
    "failure": {
        "keywords": [
            "failed",
            "failure",
            "rejected",
            "rejection",
            "setback",
            "disappointed",
            "loss",
            "lost",
            "didn't get",
            "did not get",
            "not selected",
            "demotivated after failure",
        ],
        "prototype": "rejection, disappointment, setbacks, and emotional pain after failure",
    },
    "existential": {
        "keywords": [
            "meaningless",
            "no meaning",
            "empty",
            "emptiness",
            "why live",
            "why am i doing this",
            "no motivation",
            "directionless",
            "point of life",
            "purpose",
            "existential",
        ],
        "prototype": "existential emptiness, lack of meaning, lack of motivation, and loss of purpose",
    },
    "focus": {
        "keywords": [
            "focus",
            "concentration",
            "distracted",
            "distraction",
            "procrastination",
            "mind wandering",
            "can't focus",
            "cannot focus",
            "discipline",
        ],
        "prototype": "distraction, poor concentration, mind wandering, and weak mental discipline",
    },
}

OUT_OF_SCOPE_HINTS = {
    "capital",
    "population",
    "currency",
    "weather",
    "temperature",
    "recipe",
    "calories",
    "workout",
    "protein",
    "sql",
    "javascript",
    "python",
    "algorithm",
    "debug",
    "compile",
    "football",
    "cricket",
    "movie",
    "song",
    "bitcoin",
    "stock price",
}

LIFE_GUIDANCE_HINTS = {
    "meaning",
    "meaning of life",
    "purpose",
    "purpose of life",
    "suffering",
    "injustice",
    "broken world",
    "world broken",
    "life matter",
    "does my life matter",
    "dharma",
    "svadharma",
    "duty",
    "calling",
    "moral conflict",
    "fear of losing",
    "i feel",
    "i am",
    "i regret",
    "how do i",
    "how can i",
    "struggling",
    "my mind",
    "my life",
    "emotion",
    "feeling",
    "relationship",
    "my partner",
    "work pressure",
    "anxiety",
    "anger",
    "peace",
    "purpose",
    "heartbreak",
    "lonely",
    "career",
    "exam",
    "success",
    "death",
    "passed away",
    "grief",
    "procrastination",
    "procrastinate",
    "lazy",
    "laziness",
    "focus",
    "distracted",
    "distraction",
    "doomscroll",
    "phone addiction",
    "instagram",
    "reels",
}

NON_LIFE_TASK_HINTS = {
    "playstore",
    "play store",
    "app store",
    "install app",
    "download app",
    "apk",
    "android",
    "iphone",
    "ios",
    "phone",
    "mobile",
}

GRIEF_LOSS_HINTS = {
    "death",
    "died",
    "passed away",
    "passed on",
    "they are gone",
    "gone forever",
    "no longer here",
    "funeral",
    "cremation",
    "burial",
}

GRIEF_RELATION_HINTS = {
    "mother",
    "mom",
    "father",
    "dad",
    "husband",
    "wife",
    "partner",
    "brother",
    "sister",
    "son",
    "daughter",
    "child",
    "friend",
    "loved one",
}


RELATIONAL_LOW_HINTS = {
    "relationship",
    "partner",
    "love",
    "heartbreak",
    "breakup",
    "separation",
    "lonely",
    "loneliness",
    "grief",
    "miss",
    "unwanted",
    "memories",
    "replaying",
}

EMOTIONAL_HIGH_HINTS = {
    "success",
    "achievement",
    "won",
    "promotion",
    "hike",
    "praise",
    "validated",
    "validation",
    "excited",
    "overconfident",
    "proud",
    "ego",
    "outcome",
}

PERFORMANCE_HINTS = {
    "exam",
    "interview",
    "career",
    "job",
    "result",
    "productivity",
    "skill",
    "study",
    "practice",
    "performance",
    "improve",
    "preparation",
}

GENERAL_LOW_HINTS = {
    "rejected",
    "rejection",
    "loss",
    "grief",
    "empty",
    "emptiness",
    "unwanted",
}


def classify_query_intent(query: str, embeddings: EmbeddingProvider | None = None) -> IntentRoute:
    lowered = query.lower().strip()

    if _is_out_of_scope_query(lowered):
        return IntentRoute(intent="out_of_scope", confidence=0.9, matched_keywords=[])

    if _is_non_life_practical_query(lowered):
        return IntentRoute(intent="out_of_scope", confidence=0.95, matched_keywords=[])

    primary_guidance = _detect_primary_guidance_intent(lowered)
    if primary_guidance is not None:
        intent, matched_keywords = primary_guidance
        return IntentRoute(intent=intent, confidence=0.94, matched_keywords=matched_keywords)

    emotional_state = _detect_emotional_state(lowered)
    if emotional_state is not None:
        intent, matched_keywords = emotional_state
        return IntentRoute(intent=intent, confidence=0.92, matched_keywords=matched_keywords)

    keyword_scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}

    for intent, data in INTENT_DEFINITIONS.items():
        keywords = data["keywords"]
        hits = [keyword for keyword in keywords if keyword in lowered]
        matched[intent] = hits
        keyword_scores[intent] = len(hits) / max(len(keywords), 1)

    semantic_scores = {intent: 0.0 for intent in INTENT_DEFINITIONS}
    if embeddings is not None:
        labels = list(INTENT_DEFINITIONS.keys())
        probes = [query] + [INTENT_DEFINITIONS[intent]["prototype"] for intent in labels]
        vectors = embeddings.embed_texts(probes)
        query_vec = vectors[0]
        for idx, intent in enumerate(labels, start=1):
            semantic_scores[intent] = _cosine(query_vec, vectors[idx])

    combined_scores: dict[str, float] = {}
    for intent in INTENT_DEFINITIONS:
        combined_scores[intent] = 0.7 * keyword_scores[intent] + 0.3 * semantic_scores[intent]

    best_intent = max(combined_scores, key=combined_scores.get)
    best_score = combined_scores[best_intent]
    has_keyword_signal = any(len(items) > 0 for items in matched.values())
    has_life_hint = any(token in lowered for token in LIFE_GUIDANCE_HINTS)

    if not has_keyword_signal and not has_life_hint:
        return IntentRoute(intent="out_of_scope", confidence=0.8, matched_keywords=[])

    if not has_keyword_signal and best_score < 0.11:
        return IntentRoute(intent="out_of_scope", confidence=0.7, matched_keywords=[])

    return IntentRoute(
        intent=best_intent,
        confidence=max(0.4, min(0.98, best_score)),
        matched_keywords=matched.get(best_intent, []),
    )


def map_intent_to_theme(intent: str) -> str:
    mapping = {
        "existential": "existential",
        "dharma_conflict": "dharma_conflict",
        "ego_conflict": "ego_conflict",
        "attachment": "attachment",
        "grief_loss": "grief_loss",
        "emotional_low": "emotional_low",
        "emotional_high": "emotional_high",
        "performance_context": "performance_context",
        "stress": "stress",
        "anger": "anger",
        "peace": "peace",
        "failure": "failure",
        "existential": "existential",
        "focus": "focus",
        "out_of_scope": "out_of_scope",
    }
    return mapping.get(intent, "general")


def intent_tone(intent: str) -> str:
    tones = {
        "existential": "grounding and meaning-focused",
        "dharma_conflict": "clear, steady, and identity-aware",
        "ego_conflict": "cooling, disentangling, and humbling",
        "attachment": "gentle, clarifying, and releasing",
        "grief_loss": "deeply compassionate, grounded, and respectful",
        "emotional_low": "gentle, validating, and empathetic",
        "emotional_high": "calm, grounding, and balancing",
        "performance_context": "clear, structured, and motivating",
        "stress": "stabilizing and grounding",
        "anger": "interruptive and awareness-based",
        "peace": "quieting and simplifying",
        "failure": "supportive and reflective",
        "existential": "grounding and meaningful",
        "focus": "disciplined and practical",
        "out_of_scope": "brief and redirecting",
    }
    return tones.get(intent, "calm and practical")


def _is_out_of_scope_query(lowered: str) -> bool:
    has_out_scope_hint = any(token in lowered for token in OUT_OF_SCOPE_HINTS)
    has_life_hint = any(token in lowered for token in LIFE_GUIDANCE_HINTS)
    if has_out_scope_hint and not has_life_hint:
        return True

    if lowered.startswith(("what is", "who is", "when is", "where is", "define ")) and not has_life_hint:
        return True

    return False


def _detect_primary_guidance_intent(lowered: str) -> tuple[str, list[str]] | None:
    existential_hits = [
        token
        for token in (
            "meaning of life",
            "does my life matter",
            "why is the world broken",
            "world broken",
            "broken world",
            "purpose of life",
            "suffering",
            "injustice",
            "death",
            "existence",
            "why live",
            "what is the purpose",
            "meaningless",
            "empty",
            "emptiness",
        )
        if token in lowered
    ]
    if existential_hits:
        return "existential", existential_hits

    dharma_hits = [
        token
        for token in (
            "dharma",
            "svadharma",
            "calling",
            "career or calling",
            "moral conflict",
            "should i quit",
            "should i stay",
            "right path",
            "my path",
            "what should i do",
            "family pressure",
            "duty",
        )
        if token in lowered
    ]
    if dharma_hits:
        return "dharma_conflict", dharma_hits

    ego_hits = [
        token
        for token in (
            "winning",
            "prove them wrong",
            "resentment",
            "resentful",
            "humiliated",
            "pride",
            "ego",
            "validation",
            "recognized",
            "recognition",
            "envy",
            "jealous",
            "comparison",
        )
        if token in lowered
    ]
    if ego_hits:
        return "ego_conflict", ego_hits

    attachment_hits = [
        token
        for token in (
            "fear of losing",
            "can't let go",
            "cannot let go",
            "cling",
            "clinging",
            "attached",
            "attachment",
            "afraid to lose",
            "dependent",
            "hold on",
            "need approval",
        )
        if token in lowered
    ]
    if attachment_hits:
        return "attachment", attachment_hits

    return None


def _is_non_life_practical_query(lowered: str) -> bool:
    non_life_hits = [token for token in NON_LIFE_TASK_HINTS if token in lowered]
    if not non_life_hits:
        return False

    # If there is any known life-guidance signal, this should not be rejected.
    for data in INTENT_DEFINITIONS.values():
        if any(keyword in lowered for keyword in data["keywords"]):
            return False

    life_hits = [token for token in LIFE_GUIDANCE_HINTS if token in lowered]
    if life_hits:
        return False

    return True


def _detect_emotional_state(lowered: str) -> tuple[str, list[str]] | None:
    grief_hits = [token for token in GRIEF_LOSS_HINTS if token in lowered]
    grief_relation_hits = [token for token in GRIEF_RELATION_HINTS if token in lowered]
    relational_hits = [token for token in RELATIONAL_LOW_HINTS if token in lowered]
    performance_hits = [token for token in PERFORMANCE_HINTS if token in lowered]
    high_hits = [token for token in EMOTIONAL_HIGH_HINTS if token in lowered]
    low_hits = [token for token in GENERAL_LOW_HINTS if token in lowered]

    # Irreversible bereavement should be handled separately from relationship pain.
    if grief_hits or (("died" in lowered or "death" in lowered or "passed" in lowered) and grief_relation_hits):
        return "grief_loss", list(dict.fromkeys(grief_hits + grief_relation_hits))

    # Relationship and attachment pain should route to emotional processing.
    if relational_hits:
        return "emotional_low", relational_hits

    # Success/praise/ego highs should route to grounding guidance.
    if high_hits and len(high_hits) >= len(performance_hits):
        return "emotional_high", high_hits

    # Performance situations stay strategy-oriented, even with setbacks.
    if performance_hits:
        return "performance_context", performance_hits

    # Residual emotional pain signals without performance markers.
    if low_hits:
        return "emotional_low", low_hits

    return None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
