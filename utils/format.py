import re
from typing import Any, Optional

VALID_FORMATS = {"Online", "In-Person", "Hybrid", "Unknown"}


UNKNOWN_VALUES = {
    "unknown",
    "n/a",
    "none",
    "null",
    "tbd",
    "tba",
    "to be announced",
    "to be decided",
    "to be confirmed",
    "",
}


def normalize_participation_format(raw_location: Any, text_hints: Optional[str] = None) -> str:
    """
    Normalize participation format strictly into one of:
    - 'Online'
    - 'In-Person'
    - 'Hybrid'
    - 'Unknown'

    Never assumes an event is Online merely because it was discovered on an online platform.
    Preserves Unknown when evidence is absent or inconclusive.
    """
    loc_str = str(raw_location).strip() if raw_location and isinstance(raw_location, str) else ""
    if loc_str.lower() in UNKNOWN_VALUES:
        loc_str = ""

    hint_str = str(text_hints).strip() if text_hints and isinstance(text_hints, str) else ""

    combined = []
    if loc_str:
        combined.append(loc_str)
    if hint_str:
        combined.append(hint_str)

    if not combined:
        return "Unknown"

    text = " ".join(combined).strip()
    if not text or text.lower() in UNKNOWN_VALUES:
        return "Unknown"

    text_lower = text.lower()

    # 1. Check for explicit Hybrid signals
    if re.search(r"\bhybrid\b", text_lower):
        return "Hybrid"

    has_online = bool(re.search(r"\b(online|virtual|remote|discord|zoom)\b", text_lower))
    has_physical = bool(
        re.search(
            r"\b(in-person|in person|offline|on-campus|on campus|physical venue|at the venue|on site|onsite|venue|auditorium|campus|center|centre)\b",
            text_lower,
        )
    )

    if has_online and has_physical:
        return "Hybrid"

    # 2. Check for explicit Online signals
    if has_online:
        return "Online"

    # 3. Check for explicit In-Person signals
    if has_physical:
        return "In-Person"

    # 4. Check for physical venue / address / city cues (e.g. 'San Francisco, CA', 'Bengaluru, India')
    if loc_str and loc_str.lower() not in ("online", "virtual", "remote") and loc_str.lower() not in UNKNOWN_VALUES:
        return "In-Person"

    return "Unknown"
