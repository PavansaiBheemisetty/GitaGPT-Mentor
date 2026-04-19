import re
import unicodedata


CONTROL_CHARS = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f]")
WHITESPACE = re.compile(r"[ \t]+")
LINE_SPAM = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = CONTROL_CHARS.sub("", normalized)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = WHITESPACE.sub(" ", normalized)
    normalized = LINE_SPAM.sub("\n\n", normalized)
    return normalized.strip()


def clean_section_text(text: str) -> str:
    text = normalize_text(text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.isdigit():
            continue
        if stripped.lower() in {"bhagavad-gita as it is", "bhagavad-gita"}:
            continue
        if "Copyright © 1998 The Bhaktivedanta Book Trust" in stripped:
            continue
        if "All Rights Reserved" in stripped and "Bhaktivedanta Book Trust" in stripped:
            continue
        lines.append(stripped)
    return LINE_SPAM.sub("\n\n", "\n".join(lines)).strip()
