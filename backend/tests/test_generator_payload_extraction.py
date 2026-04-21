from app.rag.generator import _extract_chat_completions_content


def test_extract_chat_content_from_plain_string() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello from model",
                }
            }
        ]
    }

    assert _extract_chat_completions_content(payload) == "Hello from model"


def test_extract_chat_content_from_block_list() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "reasoning.text", "text": "hidden chain"},
                        {"type": "text", "text": "Final answer line"},
                    ],
                }
            }
        ]
    }

    extracted = _extract_chat_completions_content(payload)
    assert "hidden chain" not in extracted
    assert "Final answer line" in extracted


def test_extract_chat_content_falls_back_to_choice_text() -> None:
    payload = {
        "choices": [
            {
                "text": "Legacy completion format",
            }
        ]
    }

    assert _extract_chat_completions_content(payload) == "Legacy completion format"


def test_extract_chat_content_falls_back_to_refusal() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "refusal": "I cannot comply with that request.",
                }
            }
        ]
    }

    assert _extract_chat_completions_content(payload) == "I cannot comply with that request."


def test_extract_chat_content_falls_back_to_top_level_output_text() -> None:
    payload = {
        "output_text": "Top-level output text",
        "choices": [],
    }

    assert _extract_chat_completions_content(payload) == "Top-level output text"
