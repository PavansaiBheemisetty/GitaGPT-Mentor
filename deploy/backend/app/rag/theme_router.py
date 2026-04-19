import math
from dataclasses import dataclass

from app.rag.embeddings import EmbeddingProvider


VerseRef = tuple[int, str]


@dataclass(frozen=True)
class ThemeRoute:
    theme: str
    confidence: float
    matched_keywords: list[str]


THEME_DEFINITIONS = {
    "existential": {
        "keywords": [
            "meaning",
            "meaning of life",
            "purpose of life",
            "suffering",
            "injustice",
            "death",
            "existence",
            "broken world",
            "world broken",
        ],
        "priority_refs": ["2.13", "2.20", "6.5", "18.66"],
        "prototype": "existential questions about suffering, death, purpose, and whether life matters",
        "lens": "meaning, suffering, and the deeper duty to continue with clarity",
    },
    "dharma_conflict": {
        "keywords": [
            "dharma",
            "svadharma",
            "calling",
            "career or calling",
            "duty",
            "moral conflict",
            "right path",
            "should i quit",
            "should i stay",
            "family pressure",
        ],
        "priority_refs": ["3.35", "18.47", "2.31", "2.31-2.38"],
        "prototype": "moral conflict, duty versus calling, and choosing one's own path without imitation",
        "lens": "svadharma, duty, and alignment with one's nature",
    },
    "ego_conflict": {
        "keywords": [
            "winning",
            "prove them wrong",
            "resentment",
            "pride",
            "ego",
            "validation",
            "recognized",
            "recognition",
            "envy",
            "comparison",
        ],
        "priority_refs": ["2.47", "3.27", "12.13"],
        "prototype": "ego-driven conflict, resentment, comparison, and identity built around winning",
        "lens": "non-attachment, humility, and action without self-importance",
    },
    "attachment": {
        "keywords": [
            "fear of losing",
            "can't let go",
            "cannot let go",
            "attached",
            "attachment",
            "cling",
            "clinging",
            "afraid to lose",
            "dependent",
            "hold on",
            "need approval",
        ],
        "priority_refs": ["2.62", "2.63", "2.70", "5.29"],
        "prototype": "attachment to outcomes, approval, success, and the fear of identity loss",
        "lens": "attachment, fear of loss, and steadying the mind through withdrawal",
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
            "funeral",
            "lost my",
        ],
        "priority_refs": ["2.13", "2.20"],
        "prototype": "grief from irreversible loss after death, where love remains but physical presence is gone",
        "lens": "finality of loss, continuity of self, and compassionate meaning-making",
    },
    "emotional_low": {
        "keywords": [
            "heartbreak",
            "love failure",
            "lonely",
            "grief",
            "loss",
            "rejected",
            "unwanted",
            "memories",
            "separation",
        ],
        "priority_refs": ["2.62", "2.63", "2.70", "2.71"],
        "prototype": "emotional pain from attachment, longing, loss, and repetitive memory loops",
        "lens": "attachment pain, impermanence, and gentle detachment",
    },
    "emotional_high": {
        "keywords": [
            "success",
            "achievement",
            "praise",
            "promotion",
            "hike",
            "ego",
            "proud",
            "overconfident",
            "validation",
        ],
        "priority_refs": ["2.48", "2.57", "2.64"],
        "prototype": "success highs can create attachment, ego-identification, and fear of future loss",
        "lens": "equanimity in success and humility in action",
    },
    "performance_context": {
        "keywords": [
            "exam",
            "interview",
            "career",
            "job",
            "result",
            "productivity",
            "skill",
            "practice",
            "performance",
        ],
        "priority_refs": ["2.47", "2.50", "6.5"],
        "prototype": "performance growth through disciplined effort, reflection, and non-attachment to outcomes",
        "lens": "karma yoga for performance and consistency",
    },
    "anger": {
        "keywords": [
            "anger",
            "angry",
            "snap",
            "snapped",
            "frustration",
            "frustrated",
            "resentment",
            "rage",
            "furious",
            "triggered",
            "irritated",
        ],
        "priority_refs": ["2.62", "2.63", "3.37"],
        "prototype": "anger grows from attachment and desire, then causes confusion and loss of judgment",
        "lens": "desire -> attachment -> anger -> confusion chain",
    },
    "stress": {
        "keywords": [
            "stress",
            "pressure",
            "anxious",
            "anxiety",
            "overwhelmed",
            "calm",
            "tension",
            "panic",
        ],
        "priority_refs": ["2.14", "2.56", "6.26"],
        "prototype": "steady mind under pressure through equanimity and returning attention to the self",
        "lens": "equanimity and steadiness under changing conditions",
    },
    "peace": {
        "keywords": [
            "peace",
            "contentment",
            "content",
            "detachment",
            "surrender",
            "restless",
            "inner peace",
            "fulfillment",
        ],
        "priority_refs": ["2.71", "5.29", "18.66"],
        "prototype": "inner peace comes from detachment from craving and surrendering outcomes to the divine",
        "lens": "detachment, devotion, and surrender",
    },
    "failure": {
        "keywords": [
            "failure",
            "failed",
            "rejected",
            "rejection",
            "setback",
            "disappointed",
            "loss",
            "didn't get",
            "did not get",
            "not selected",
        ],
        "priority_refs": ["2.47", "2.38"],
        "prototype": "responding to failure by acting with discipline without attaching identity to outcomes",
        "lens": "duty-focused action without result-identity",
    },
    "existential": {
        "keywords": [
            "meaningless",
            "empty",
            "emptiness",
            "purpose",
            "directionless",
            "no motivation",
            "why am i doing this",
            "point of life",
            "existential",
        ],
        "priority_refs": ["6.5", "18.66"],
        "prototype": "rebuilding inner meaning through self-upliftment, responsibility, and surrender of paralysis",
        "lens": "self-upliftment, surrender, and meaningful responsibility",
    },
    "focus": {
        "keywords": [
            "focus",
            "discipline",
            "concentration",
            "distraction",
            "mind wandering",
            "habit",
            "consistency",
            "procrastination",
        ],
        "priority_refs": ["6.5", "6.26"],
        "prototype": "mind control through repeated redirection and disciplined self-effort",
        "lens": "mind training and disciplined redirection",
    },
    "general": {
        "keywords": [],
        "priority_refs": [],
        "prototype": "dharma, devotion, clarity, and wise action in daily life",
        "lens": "general Gita guidance",
    },
}


def classify_query_theme(query: str, embeddings: EmbeddingProvider | None = None) -> ThemeRoute:
    lowered = query.lower()
    keyword_scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}

    for theme, data in THEME_DEFINITIONS.items():
        keywords = data["keywords"]
        hits = [keyword for keyword in keywords if keyword in lowered]
        matched[theme] = hits
        keyword_scores[theme] = len(hits) / max(len(keywords), 1)

    semantic_scores = {theme: 0.0 for theme in THEME_DEFINITIONS}
    if embeddings is not None:
        labels = list(THEME_DEFINITIONS.keys())
        probes = [query] + [THEME_DEFINITIONS[theme]["prototype"] for theme in labels]
        vectors = embeddings.embed_texts(probes)
        query_vec = vectors[0]
        for idx, theme in enumerate(labels, start=1):
            semantic_scores[theme] = _cosine(query_vec, vectors[idx])

    combined_scores: dict[str, float] = {}
    for theme in THEME_DEFINITIONS:
        combined_scores[theme] = 0.65 * keyword_scores[theme] + 0.35 * semantic_scores[theme]

    best_theme = max(combined_scores, key=combined_scores.get)
    best_score = combined_scores[best_theme]
    has_keyword_signal = any(len(items) > 0 for items in matched.values())

    if best_theme != "general" and not has_keyword_signal and best_score < 0.12:
        return ThemeRoute(theme="general", confidence=0.35, matched_keywords=[])

    return ThemeRoute(
        theme=best_theme,
        confidence=max(0.35, min(0.98, best_score)),
        matched_keywords=matched.get(best_theme, []),
    )


def theme_seed_verses(theme: str) -> set[VerseRef]:
    data = THEME_DEFINITIONS.get(theme, THEME_DEFINITIONS["general"])
    seeds: set[VerseRef] = set()
    for ref in data["priority_refs"]:
        seeds.update(_expand_reference(ref))
    return seeds


def theme_lens(theme: str) -> str:
    data = THEME_DEFINITIONS.get(theme, THEME_DEFINITIONS["general"])
    return str(data["lens"])


def expand_verse_label(label: str) -> list[str]:
    normalized = label.replace("–", "-").strip()
    if "-" not in normalized:
        return [normalized]
    start, end = normalized.split("-", 1)
    if start.isdigit() and end.isdigit():
        return [str(value) for value in range(int(start), int(end) + 1)]
    return [normalized]


def chunk_matches_seed(*, chapter: int, verse_label: str, seed_refs: set[VerseRef]) -> bool:
    for verse in expand_verse_label(verse_label):
        if (chapter, verse) in seed_refs:
            return True
    return False


def _expand_reference(ref: str) -> list[VerseRef]:
    chapter_str, verse_label = ref.split(".", 1)
    chapter = int(chapter_str)
    return [(chapter, verse) for verse in expand_verse_label(verse_label)]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
