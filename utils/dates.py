import datetime
import re
from typing import Optional, Tuple

from dateutil import parser

# Patterns for relative countdown text that must NOT be parsed as calendar dates
RELATIVE_TIME_REGEX = re.compile(
    r"\b\d+\s*(?:days?|hours?|mins?|minutes?|secs?|seconds?)\s*(?:left|ago|to\s*go)\b",
    re.IGNORECASE,
)

MONTH_ORDER = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _has_explicit_time(text: str) -> bool:
    """Check if a date string includes an explicit non-date time component."""
    return bool(re.search(r"[T\s]\d{1,2}:\d{2}(?::\d{2})?", text))


def parse_iso_to_utc(date_input, is_deadline: bool = False) -> Optional[datetime.datetime]:
    """
    Parse a date string or datetime into a timezone-aware UTC datetime.
    If is_deadline=True and input has no explicit time component (date-only deadline),
    treats the deadline as end-of-day (23:59:59 UTC).
    """
    if not date_input:
        return None
    if isinstance(date_input, datetime.datetime):
        if date_input.tzinfo is None:
            dt = date_input.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = date_input.astimezone(datetime.timezone.utc)
        if is_deadline and dt.hour == 0 and dt.minute == 0 and dt.second == 0:
            dt = dt.replace(hour=23, minute=59, second=59)
        return dt

    if not isinstance(date_input, str):
        return None

    cleaned = date_input.strip()
    if not cleaned or cleaned.lower() == "unknown":
        return None

    # Reject relative strings
    if RELATIVE_TIME_REGEX.search(cleaned):
        return None

    try:
        has_time = _has_explicit_time(cleaned)
        normalized = normalize_date(cleaned)
        if not normalized:
            normalized = cleaned

        dt = parser.parse(normalized, fuzzy=True)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)

        # Date-only deadline: treat as end of day in UTC
        if is_deadline and not has_time:
            dt = dt.replace(hour=23, minute=59, second=59)

        return dt
    except Exception:
        return None


def parse_date_range(range_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse date range text like 'May 05 - Jun 11, 2026' or 'Dec 20 - Jan 15, 2027' into (start_iso, end_iso).
    Corrects cross-year date ranges when month rollovers occur.
    """
    if not range_text or not isinstance(range_text, str):
        return None, None

    cleaned = range_text.strip()
    if not cleaned or cleaned.lower() == "unknown":
        return None, None

    if RELATIVE_TIME_REGEX.search(cleaned):
        return None, None

    range_parts = re.split(r"\s+[-–—]\s+|\s+to\s+", cleaned, flags=re.IGNORECASE)
    if len(range_parts) >= 2:
        start_part = range_parts[0].strip()
        end_part = range_parts[-1].strip()

        year_start = re.search(r"\b(20\d\d)\b", start_part)
        year_end = re.search(r"\b(20\d\d)\b", end_part)
        month_start = re.search(r"\b([A-Za-z]+)\b", start_part)
        month_end = re.search(r"\b([A-Za-z]+)\b", end_part)

        m_start_idx = MONTH_ORDER.get(month_start.group(1).lower()) if month_start else None
        m_end_idx = MONTH_ORDER.get(month_end.group(1).lower()) if month_end else None

        if year_start and not year_end:
            base_year = int(year_start.group(1))
            if m_start_idx and m_end_idx and m_start_idx > m_end_idx:
                end_part = f"{end_part} {base_year + 1}"
            else:
                end_part = f"{end_part} {base_year}"
        elif year_end and not year_start:
            base_year = int(year_end.group(1))
            if m_start_idx and m_end_idx and m_start_idx > m_end_idx:
                start_part = f"{start_part} {base_year - 1}"
            else:
                start_part = f"{start_part} {base_year}"

        if month_start and not month_end:
            end_part = f"{month_start.group(1)} {end_part}"

        start_iso = None
        end_iso = None
        try:
            start_iso = parser.parse(start_part, fuzzy=True).isoformat()
        except Exception:
            pass
        try:
            end_iso = parser.parse(end_part, fuzzy=True).isoformat()
        except Exception:
            pass
        return start_iso, end_iso

    try:
        single_iso = parser.parse(cleaned, fuzzy=True).isoformat()
        return None, single_iso
    except Exception:
        return None, None


def normalize_date(date_text: Optional[str]) -> Optional[str]:
    """Normalize human-readable or partial dates to ISO 8601 string."""
    if not date_text or not isinstance(date_text, str):
        return None

    cleaned = date_text.strip()
    if not cleaned or cleaned.lower() == "unknown":
        return None

    if RELATIVE_TIME_REGEX.search(cleaned):
        return None

    # Handle date ranges such as 'May 05 - Jun 11, 2026' or 'Dec 20 - Jan 15, 2027'
    range_parts = re.split(r"\s+[-–—]\s+|\s+to\s+", cleaned, flags=re.IGNORECASE)
    if len(range_parts) >= 2:
        _, end_iso = parse_date_range(cleaned)
        return end_iso

    try:
        return parser.parse(cleaned, fuzzy=True).isoformat()
    except Exception:
        return None


def evaluate_hackathon_status(
    deadline: Optional[str] = None,
    reg_starts_at: Optional[str] = None,
    reg_ends_at: Optional[str] = None,
    starts_at: Optional[str] = None,
    ends_at: Optional[str] = None,
    source_status: Optional[str] = None,
    as_of: Optional[datetime.datetime] = None,
) -> str:
    """
    Centralized, deterministic status categorization rule engine.
    Returns one of: 'open', 'upcoming', 'ended', or 'unknown'.

    Guarantees:
    - Never classifies a hackathon as 'open' or 'upcoming' if its registration deadline has passed.
    - Treats date-only deadlines as end-of-day (23:59:59 UTC).
    - Never confuses event end dates with registration deadlines.
    - Never assumes an unknown deadline means registration is open.
    - Supports controlled clock via 'as_of' for deterministic testing.
    """
    now = as_of or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)

    # If source explicitly reported 'ended', respect it
    if source_status and source_status.lower() in ("ended", "past", "closed"):
        return "ended"

    # Effective registration deadline: prioritize explicit registration end, then general deadline
    # Do NOT confuse event end dates with registration deadlines!
    effective_deadline_str = reg_ends_at or deadline
    deadline_utc = parse_iso_to_utc(effective_deadline_str, is_deadline=True) if effective_deadline_str else None

    # Case 1: Verified registration deadline is present
    if deadline_utc:
        if deadline_utc < now:
            return "ended"

        # Check if registration has not opened yet
        reg_start_utc = parse_iso_to_utc(reg_starts_at)
        if reg_start_utc and reg_start_utc > now:
            return "upcoming"

        # If source explicitly indicates upcoming
        if source_status and source_status.lower() == "upcoming":
            return "upcoming"

        # Verified future deadline and registration has opened (or no reg_start specified) -> OPEN
        return "open"

    # Case 2: Deadline is unknown, but event end or start is known
    # If the event itself has already ended, we know it is ended
    if ends_at:
        end_utc = parse_iso_to_utc(ends_at, is_deadline=True)
        if end_utc and end_utc < now:
            return "ended"

    if starts_at:
        start_utc = parse_iso_to_utc(starts_at)
        if start_utc:
            if start_utc > now:
                return "upcoming"
            # If the event has already started and we have no registration deadline,
            # we do not assume open registration
            return "unknown"

    return "unknown"
