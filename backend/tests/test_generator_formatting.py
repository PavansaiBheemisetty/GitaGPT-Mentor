from app.models.chat import RetrievedChunk
from app.rag.generator import _enforce_contract, _post_process_answer


def test_heading_variants_are_canonicalized():
    question = "I feel overwhelmed and wondering if life is meaningless"
    raw = """- Direct Insight.
You are grappling with impermanence and meaning.

- Gita Wisdom.
BG 2.8: Arjuna describes deep sorrow that material success cannot remove.

3. Why This Happens
Attachment and fear of loss amplify existential pain.

4. Practical Reflection
- acknowledge your emotions
- ground attention in the present
- choose one meaningful responsibility
- seek support

Closing Line (Punchline)
*Meaning returns through aligned action.*
"""

    chunks = [
        RetrievedChunk(
            chunk_id="x",
            chapter=2,
            verse="8",
            type="translation",
            text="text",
            score=0.9,
            source_pages=[1],
        )
    ]

    out = _enforce_contract(raw, question=question, chunks=chunks, intent="existential", theme="existential")

    assert "Direct Insight (Human Tone)" in out
    assert "Gita Wisdom (Verse Reference + Meaning)" in out
    assert "Why This Happens (Mechanism)" in out
    assert "Practical Reflection (Actionable Steps)" in out
    assert "Closing Line (Punchline)" in out


def test_closing_punchline_label_is_stripped():
    raw = """Direct Insight (Human Tone)
Deep insight.

Gita Wisdom (Verse Reference + Meaning)
BG 2.47: Work without clinging.

Why This Happens (Mechanism)
Attachment narrows judgment.

Practical Reflection (Actionable Steps)
- breathe
- reflect

Closing Punchline: Peace is not won or lost, but found in stillness.
"""

    out = _post_process_answer(raw, question="Why is the mind restless?")

    assert "Closing Punchline" not in out
    assert "Closing Line (Punchline)" in out
    closing = out.split("Closing Line (Punchline)\n", 1)[1].strip().strip("*")
    assert "\n" not in closing
    assert 10 <= len(closing.rstrip(".!?").split()) <= 16


def test_rebuilds_broken_inline_sections_into_strict_layout():
    raw = (
        "Direct Insight (Human Tone) The world feels heavy when suffering seems endless. "
        "Gita Wisdom (Verse Reference + Meaning) BG 2.14: stay steady through changing pain and relief. "
        "Why This Happens (Mechanism) Attachment to control makes responsibility feel crushing. "
        "Practical Reflection (Actionable Steps) observe attachment. reduce exposure to triggers. return to one duty. "
        "Closing Line (Punchline) this mind can become steady."
    )

    out = _post_process_answer(raw, question="Why does suffering make life feel meaningless?")

    assert "Direct Insight (Human Tone)\n" in out
    assert "Gita Wisdom (Verse Reference + Meaning)\n" in out
    assert "Why This Happens (Mechanism)\n" in out
    assert "Practical Reflection (Actionable Steps)\n" in out
    assert "Closing Line (Punchline)\n" in out
    assert "- " in out
    assert "\n*" in out


def test_punchline_is_regenerated_when_repeating_previous_sentence():
    raw = """Direct Insight (Human Tone)
You are entangled in outcome pressure.

Gita Wisdom (Verse Reference + Meaning)
BG 2.47: Act without attachment to outcomes.
This applies here because your attention is trapped by outcomes.

Why This Happens (Mechanism)
Attachment to outcomes tightens fear and clouds discernment in action.

Practical Reflection (Actionable Steps)
- observe attachment before action
- perform one duty without bargaining for results
- track steadiness of action, not applause

Closing Line (Punchline)
*Attachment to outcomes tightens fear and clouds discernment in action.*
"""

    out = _post_process_answer(raw, question="Why do I panic before outcomes?", theme="attachment")

    closing = out.split("Closing Line (Punchline)\n", 1)[1].strip().strip("*")
    mechanism = out.split("Why This Happens (Mechanism)\n", 1)[1].split(
        "\n\nPractical Reflection (Actionable Steps)", 1
    )[0].strip()

    assert closing.lower() != mechanism.lower()
    assert "\n" not in closing
    assert 10 <= len(closing.rstrip(".!?").split()) <= 16


def test_practical_steps_strip_generic_wellness_phrases():
    raw = """Direct Insight (Human Tone)
You are scattered between desire and duty.

Gita Wisdom (Verse Reference + Meaning)
BG 3.35: Better your own duty than imitation.
This applies here because borrowed goals are creating inner conflict.

Why This Happens (Mechanism)
Comparison and attachment convert preference into anxiety and indecision.

Practical Reflection (Actionable Steps)
- practice self-care
- explore hobbies
- build relationships

Closing Line (Punchline)
*Clarity grows when duty is chosen from nature, not comparison.*
"""

    out = _post_process_answer(raw, question="I feel lost between options", theme="dharma_conflict")
    lowered = out.lower()

    assert "practice self-care" not in lowered
    assert "explore hobbies" not in lowered
    assert "build relationships" not in lowered
    assert "dharma" in lowered or "duty" in lowered


def test_wisdom_section_adds_direct_applicability_when_missing():
    raw = """Direct Insight (Human Tone)
You are facing pressure and uncertainty.

Gita Wisdom (Verse Reference + Meaning)
BG 2.56: Steady one remains under changing conditions.

Why This Happens (Mechanism)
Outcome-clinging amplifies stress and weakens judgment.

Practical Reflection (Actionable Steps)
- observe the mind before reacting
- execute one duty with steady focus
- release fixation on immediate reward

Closing Line (Punchline)
*Steadiness appears when duty leads and fear stops commanding action.*
"""

    out = _post_process_answer(raw, question="How do I stay steady under pressure?", theme="stress")

    wisdom_block = out.split("Gita Wisdom (Verse Reference + Meaning)\n", 1)[1].split(
        "\n\nWhy This Happens (Mechanism)", 1
    )[0]
    assert "This applies here because" in wisdom_block


def test_numbness_not_mislabeled_as_sattva():
    raw = """Direct Insight (Human Tone)
You feel emotionally numb and detached from life.

Gita Wisdom (Verse Reference + Meaning)
BG 14.6: Sattva binds through light and clarity.

Why This Happens (Mechanism)
This numbness is sattva because your mind is calm and still.

Practical Reflection (Actionable Steps)
- observe your mind
- do one duty steadily
- regulate sensory exposure

Closing Line (Punchline)
*Clarity grows when attachment loosens and duty is performed with steadiness.*
"""

    out = _post_process_answer(raw, question="Why do I feel emotionally numb and apathetic?", theme="existential")
    lowered = out.lower()

    assert "sattva because" not in lowered
    assert "tamas" in lowered


def test_malformed_asterisk_prefixes_are_removed():
    raw = """Direct Insight (Human Tone)
**. You are exhausted by role-pressure.

Gita Wisdom (Verse Reference + Meaning)
**. BG 18.47: Better one's own duty, though imperfect.

Why This Happens (Mechanism)
**. Attachment to role-image is draining your discernment.

Practical Reflection (Actionable Steps)
**.
- observe attachment
- act from duty
- release outcome-ownership

Closing Line (Punchline)
*Duty with detachment protects both service and inner steadiness.*
"""

    out = _post_process_answer(raw, question="I feel burnt out serving everyone", theme="dharma_conflict")
    assert "**." not in out
    assert "\n- " in out


def test_prompt_feeling_style_punchline_is_regenerated_to_gita_summary():
    raw = """Direct Insight (Human Tone)
You are carrying too much and losing your center.

Gita Wisdom (Verse Reference + Meaning)
BG 2.47: You govern action, not the total field of results.
This applies here because outcome pressure is overriding your duty clarity.

Why This Happens (Mechanism)
Attachment to role-success fuses service with identity and creates resentment.

Practical Reflection (Actionable Steps)
- notice role-attachment before reacting
- perform one duty with detachment from approval
- restore sense-discipline before key decisions

Closing Line (Punchline)
*You are feeling burnout and resentment while serving everyone around you.*
"""

    out = _post_process_answer(raw, question="I feel burnt out while caring for everyone", theme="dharma_conflict")
    closing = out.split("Closing Line (Punchline)\n", 1)[1].strip().strip("*").lower()

    assert "you are feeling" not in closing
    assert "burnout" not in closing
    assert any(term in closing for term in ("dharma", "duty", "detachment", "attachment", "karma"))
    assert 10 <= len(closing.rstrip(".!?").split()) <= 16
