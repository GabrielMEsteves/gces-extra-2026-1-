from __future__ import annotations

import re


def normalize_year(year_text: str) -> int | None:
    cleaned = year_text.strip()
    if len(cleaned) == 2:
        value = int(cleaned)
        return 2000 + value if value <= 79 else 1900 + value
    if len(cleaned) == 4:
        return int(cleaned)
    return None


def extract_reference_period(text: str) -> tuple[int | None, int | None]:
    normalized = re.sub(r"\s+", " ", text)
    patterns = [
        r"\b([1-4])\s*T\s*[-_/ ]*\s*(20\d{2}|\d{2})\b",
        r"\b(20\d{2}|\d{2})\s*[-_/ ]*\s*([1-4])\s*T\b",
        r"\b([1-4])[ºo]?\s+trimestre\s+de\s+(20\d{2})\b",
        r"\bprimeiro trimestre de (20\d{2})\b",
        r"\bsegundo trimestre de (20\d{2})\b",
        r"\bterceiro trimestre de (20\d{2})\b",
        r"\bquarto trimestre de (20\d{2})\b",
    ]

    match = re.search(patterns[0], normalized, flags=re.IGNORECASE)
    if match:
        return normalize_year(match.group(2)), int(match.group(1))

    match = re.search(patterns[1], normalized, flags=re.IGNORECASE)
    if match:
        return normalize_year(match.group(1)), int(match.group(2))

    match = re.search(patterns[2], normalized, flags=re.IGNORECASE)
    if match:
        return int(match.group(2)), int(match.group(1))

    textual = {
        patterns[3]: 1,
        patterns[4]: 2,
        patterns[5]: 3,
        patterns[6]: 4,
    }
    for pattern, quarter in textual.items():
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return int(match.group(1)), quarter

    return None, None
