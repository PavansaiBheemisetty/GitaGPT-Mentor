from app.rag.normalizer import clean_section_text, normalize_text


def test_normalize_text_removes_control_chars_and_collapses_spaces():
    assert normalize_text("Duty\u0000   and\r\nfocus") == "Duty and\nfocus"


def test_clean_section_text_removes_page_numbers_and_repeated_title():
    text = "Bhagavad-Gita As It Is\n12\nA useful line"
    assert clean_section_text(text) == "A useful line"
