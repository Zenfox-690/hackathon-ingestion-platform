import datetime
import re
from typing import Optional, Tuple

from dateutil import parser


def parse_iso_to_utc(date_input) -> Optional[datetime.datetime]:
    """Parse a date string or datetime into a timezone-aware UTC datetime."""
    if not date_input:
        return None
    if isinstance(date_input, datetime.datetime):
        if date_input.tzinfo is None:
            return date_input.replace(tzinfo=datetime.timezone.utc)
        return date_input.astimezone(datetime.timezone.utc)

    if not isinstance(date_input, str):
        return None

    cleaned = date_input.strip()
    if not cleaned or cleaned.lower() == "unknown":
        return None

    try:
        # If it's a date range, extract the deadline (end part)
        normalized = normalize_date(cleaned)
        if not normalized:
            normalized = cleaned

        dt = parser.parse(normalized, fuzzy=True)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        return None


def parse_date_range(range_text: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse date range text like 'May 05 - Jun 11, 2026' into (start_iso, end_iso)."""
    if not range_text or not isinstance(range_text, str):
        return None, None

    cleaned = range_text.strip()
    if not cleaned or cleaned.lower() == "unknown":
        return None, None

    range_parts = re.split(r"\s+[-–—]\s+|\s+to\s+", cleaned, flags=re.IGNORECASE)
    if len(range_parts) >= 2:
        start_part = range_parts[0].strip()
        end_part = range_parts[-1].strip()

        year_start = re.search(r"\b(20\d\d)\b", start_part)
        year_end = re.search(r"\b(20\d\d)\b", end_part)
        if year_start and not year_end:
            end_part = f"{end_part} {year_start.group(1)}"
        elif year_end and not year_start:
            start_part = f"{start_part} {year_end.group(1)}"

        month_start = re.search(r"\b([A-Za-z]+)\b", start_part)
        month_end = re.search(r"\b([A-Za-z]+)\b", end_part)
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

    # Handle date ranges such as 'May 05 - Jun 11, 2026' or 'Jun 01 - 15, 2026'
    range_parts = re.split(r"\s+[-–—]\s+|\s+to\s+", cleaned, flags=re.IGNORECASE)
    if len(range_parts) >= 2:
        start_part = range_parts[0].strip()
        end_part = range_parts[-1].strip()

        year_start = re.search(r"\b(20\d\d)\b", start_part)
        year_end = re.search(r"\b(20\d\d)\b", end_part)
        if year_start and not year_end:
            end_part = f"{end_part} {year_start.group(1)}"
        elif year_end and not year_start:
            start_part = f"{start_part} {year_end.group(1)}"

        month_start = re.search(r"\b([A-Za-z]+)\b", start_part)
        month_end = re.search(r"\b([A-Za-z]+)\b", end_part)
        if month_start and not month_end:
            end_part = f"{month_start.group(1)} {end_part}"

        try:
            return parser.parse(end_part, fuzzy=True).isoformat()
        except Exception:
            pass

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
    - Never assumes an unknown deadline means registration is open.
    - Supports controlled clock via 'as_of' for deterministic testing.
    """
    now = as_of or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)

    # If source explicitly reported 'ended', respect it
    if source_status and source_status.lower() in ("ended", "past", "closed"):
        return "ended"

    # Effective deadline: prioritize explicit registration end, then general deadline, then event end
    effective_deadline_str = reg_ends_at or deadline or ends_at
    deadline_utc = parse_iso_to_utc(effective_deadline_str)

    # Case 1: Verified deadline is in the past -> ENDED
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

    # Case 2: Deadline is unknown
    # Do not invent dates or assume open
    if starts_at:
        start_utc = parse_iso_to_utc(starts_at)
        if start_utc:
            if start_utc < now:
                return "ended"
            return "upcoming"

    return "unknown"
