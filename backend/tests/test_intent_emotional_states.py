from app.models.chat import RetrievedChunk
from app.rag.generator import _is_theme_action_valid, _is_theme_mechanism_valid, _template_answer
from app.rag.intent_router import classify_query_intent, map_intent_to_theme


def _sample_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id="gita-2-13",
            chapter=2,
            verse="13",
            type="translation",
            text="Just as the embodied self passes through childhood, youth, and old age, so too it passes to another body.",
            score=0.92,
            source_pages=[1],
        )
    ]


def test_grief_loss_detected_for_death_language():
    route = classify_query_intent("My mother passed away and I feel broken every night")

    assert route.intent == "grief_loss"
    assert map_intent_to_theme(route.intent) == "grief_loss"


def test_grief_loss_precedence_over_emotional_low():
    route = classify_query_intent(
        "I feel lonely and heartbroken after my father died; I keep replaying memories"
    )

    assert route.intent == "grief_loss"


def test_grief_loss_generation_avoids_performance_language():
    answer = _template_answer(
        "My wife passed away and I do not know how to live with this absence",
        _sample_chunks(),
        intent="grief_loss",
        theme="grief_loss",
    )

    lowered = answer.lower()
    assert "grief" in lowered
    assert any(token in lowered for token in ("absence", "memory", "physically"))
    assert all(token not in lowered for token in ("next attempt", "optimize", "productivity", "exam"))


def test_grief_loss_validation_rules_are_specific():
    valid_mechanism = (
        "Memories come in waves because irreversible absence changes daily life, "
        "and love has to be carried in a new form."
    )
    invalid_mechanism = "Result anxiety comes from exam pressure and deadline overload."

    assert _is_theme_mechanism_valid("grief_loss", valid_mechanism)
    assert not _is_theme_mechanism_valid("grief_loss", invalid_mechanism)

    valid_actions = "Pause, breathe, and honor one memory while grounding in the present."
    invalid_actions = "Optimize your strategy and schedule the next attempt immediately."

    assert _is_theme_action_valid("grief_loss", valid_actions)
    assert not _is_theme_action_valid("grief_loss", invalid_actions)


def test_non_life_practical_query_is_out_of_scope():
    route = classify_query_intent("how to install an app from playstore?")

    assert route.intent == "out_of_scope"


def test_existential_questions_stay_in_scope():
    route = classify_query_intent("Why is there suffering and does my life matter?")

    assert route.intent == "existential"


def test_dharma_conflict_is_classified_separately():
    route = classify_query_intent("My career feels like duty, but it is not my calling")

    assert route.intent == "dharma_conflict"


def test_attachment_and_ego_signals_route_out_of_generic_scope():
    attachment = classify_query_intent("I am afraid to lose the success I built and cannot let go")
    ego = classify_query_intent("I need to win and prove them wrong")

    assert attachment.intent == "attachment"
    assert ego.intent == "ego_conflict"


def test_procrastination_with_phone_context_is_not_out_of_scope():
    route = classify_query_intent("I keep procrastinating because of phone reels and can't focus")

    assert route.intent in {"focus", "performance_context"}
