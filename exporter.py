import datetime
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import db.store as store
from utils.dates import evaluate_hackathon_status, normalize_date
from utils.format import normalize_participation_format

DEFAULT_EXPORT_PATH = Path("data/hackathons.json")
FRONTEND_EXPORT_PATH = Path("frontend/public/data/hackathons.json")


def load_existing_catalog(catalog_path: Path = DEFAULT_EXPORT_PATH) -> Optional[Dict[str, Any]]:
    """Load previously validated public catalog from disk if present."""
    if not catalog_path.exists():
        return None
    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "metadata" in data and "hackathons" in data:
                return data
    except Exception as e:
        print(f"[EXPORTER] Warning: could not load existing catalog at {catalog_path}: {e}")
    return None


KNOWN_SECTION_NAMES = {
    "your hackathons",
    "all upcoming hackathons",
    "all past hackathons",
    "all open hackathons",
    "all opening hackathons",
}


def is_section_link_item(item: Dict[str, Any]) -> bool:
    if item.get("is_section_link"):
        return True
    name = (item.get("name") or item.get("title") or "").strip().lower()
    link = (item.get("link") or item.get("url") or "").strip().lower()
    if name in KNOWN_SECTION_NAMES:
        return True
    if any(p in link for p in ["/hackathons/applied", "/hackathons/upcoming", "/hackathons/past", "/hackathons/open"]):
        return True
    return False


def merge_hackathon_records(
    baseline_records: List[Dict[str, Any]],
    incoming_records: List[Dict[str, Any]],
    as_of: Optional[datetime.datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Merge incoming validated records with baseline records.
    - Merges by stable identity (fingerprint or canonical link).
    - Preserves baseline records if an incoming source was absent or failed.
    - Enriches existing records when new data has more complete information.
    - Strictly re-evaluates status (open, upcoming, ended, unknown) against reference time.
    - Filters out section navigation links from the main hackathon listings.
    """
    by_identity: Dict[str, Dict[str, Any]] = {}

    # Seed with baseline records (excluding section navigation links)
    for item in baseline_records:
        if is_section_link_item(item):
            continue
        key = item.get("fingerprint") or item.get("id") or item.get("link")
        if key:
            by_identity[key] = dict(item)

    # Merge incoming records
    for inc in incoming_records:
        if is_section_link_item(inc):
            continue
        key = inc.get("fingerprint") or inc.get("id") or inc.get("link")
        if not key:
            continue

        if key in by_identity:
            curr = by_identity[key]
            merged = dict(curr)
            for field in (
                "description",
                "prize",
                "location",
                "deadline",
                "reg_starts_at",
                "reg_ends_at",
                "starts_at",
                "ends_at",
                "source_status",
            ):
                inc_val = inc.get(field)
                curr_val = curr.get(field)
                if inc_val and inc_val not in ("Unknown", ""):
                    if not curr_val or curr_val in ("Unknown", ""):
                        merged[field] = inc_val

            # Tags: combine and deduplicate
            merged_tags = sorted(list(set(curr.get("tags", []) + inc.get("tags", []))))
            merged["tags"] = merged_tags

            # Benefits: prefer incoming benefits if non-empty, otherwise preserve current
            inc_b = inc.get("benefits")
            curr_b = curr.get("benefits")
            if inc_b:
                merged["benefits"] = inc_b
            elif curr_b:
                merged["benefits"] = curr_b
            else:
                merged["benefits"] = []

            # Update updated_at timestamp
            merged["updated_at"] = inc.get("updated_at") or datetime.datetime.now(datetime.timezone.utc).isoformat()
            by_identity[key] = merged
        else:
            by_identity[key] = dict(inc)

    final_records = []
    for item in by_identity.values():
        clean_item = dict(item)
        fp = clean_item.get("fingerprint") or clean_item.get("id") or ""
        clean_item["fingerprint"] = fp
        clean_item["id"] = fp
        clean_item["title"] = clean_item.get("name") or clean_item.get("title") or ""
        clean_item["url"] = clean_item.get("link") or clean_item.get("url") or ""
        clean_item["location"] = normalize_participation_format(clean_item.get("location"))
        clean_item["benefits"] = clean_item.get("benefits") or []

        # Dynamic, timezone-aware status calculation
        status = evaluate_hackathon_status(
            deadline=clean_item.get("deadline"),
            reg_starts_at=clean_item.get("reg_starts_at"),
            reg_ends_at=clean_item.get("reg_ends_at"),
            starts_at=clean_item.get("starts_at"),
            ends_at=clean_item.get("ends_at"),
            source_status=clean_item.get("source_status"),
            as_of=as_of,
        )
        clean_item["status"] = status
        final_records.append(clean_item)

    # Sort: Actionable (open/upcoming) first, then by deadline ascending, then ended
    def sort_order_key(x):
        st = x.get("status", "unknown")
        # Priority: open (0), upcoming (1), unknown (2), ended (3)
        priority_map = {"open": 0, "upcoming": 1, "unknown": 2, "ended": 3}
        pri = priority_map.get(st, 2)
        dl = x.get("deadline") or "9999"
        norm = normalize_date(dl) or (dl if "T" in dl else "9999-99-99")
        return (pri, norm)

    final_records.sort(key=sort_order_key)
    return final_records


def build_catalog_payload(
    records: List[Dict[str, Any]], supplementary_links: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """Build the public JSON structure with sanitized metadata."""
    sources_count: Dict[str, int] = {}
    formats_count: Dict[str, int] = {"Online": 0, "In-Person": 0, "Hybrid": 0, "Unknown": 0}
    open_count = 0
    upcoming_count = 0
    ended_count = 0
    unknown_count = 0
    total_benefits = 0

    sanitized_records = []
    for r in records:
        if is_section_link_item(r):
            continue

        src = r.get("source", "Unknown")
        sources_count[src] = sources_count.get(src, 0) + 1

        loc = normalize_participation_format(r.get("location"))
        formats_count[loc] = formats_count.get(loc, 0) + 1

        st = r.get("status", "unknown")
        if st == "open":
            open_count += 1
        elif st == "upcoming":
            upcoming_count += 1
        elif st == "ended":
            ended_count += 1
        else:
            unknown_count += 1

        b_list = r.get("benefits") or []
        total_benefits += len(b_list)

        sanitized = {
            "id": r.get("id") or r.get("fingerprint"),
            "fingerprint": r.get("fingerprint") or r.get("id"),
            "name": r.get("name") or r.get("title", ""),
            "title": r.get("title") or r.get("name", ""),
            "link": r.get("link") or r.get("url", ""),
            "url": r.get("url") or r.get("link", ""),
            "source": r.get("source", ""),
            "deadline": r.get("deadline") or "Unknown",
            "reg_starts_at": r.get("reg_starts_at") or "",
            "reg_ends_at": r.get("reg_ends_at") or "",
            "starts_at": r.get("starts_at") or "",
            "ends_at": r.get("ends_at") or "",
            "description": r.get("description") or "",
            "tags": r.get("tags") or [],
            "prize": r.get("prize") or "Unknown",
            "location": loc,
            "status": st,
            "benefits": b_list,
            "created_at": r.get("created_at") or "",
            "updated_at": r.get("updated_at") or "",
        }
        sanitized_records.append(sanitized)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {
        "metadata": {
            "version": "1.0.0",
            "generated_at": now_iso,
            "total_count": len(sanitized_records),
            "active_count": open_count + upcoming_count,
            "open_count": open_count,
            "upcoming_count": upcoming_count,
            "ended_count": ended_count,
            "unknown_count": unknown_count,
            "sources": sources_count,
            "formats": formats_count,
            "benefits_count": total_benefits,
            "supplementary_links": supplementary_links or [],
        },
        "hackathons": sanitized_records,
    }


def export_public_catalog(
    output_path: Path = DEFAULT_EXPORT_PATH,
    incoming_records: Optional[List[Dict[str, Any]]] = None,
    allow_empty_if_no_baseline: bool = False,
    as_of: Optional[datetime.datetime] = None,
    conn_override: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    """
    Exports the public catalog to disk atomically.
    Ensures failure-safety: if an all-source ingestion failure occurs,
    does NOT erase the existing known-good catalog.
    """
    if isinstance(output_path, str):
        output_path = Path(output_path)

    existing_catalog = load_existing_catalog(output_path)
    baseline_records = existing_catalog.get("hackathons", []) if existing_catalog else []

    # If incoming records not provided, load from SQLite store
    if incoming_records is None:
        incoming_records = store.get_all_public_hackathons(include_sections=False, conn_override=conn_override)

    supplementary_links = store.get_supplementary_links(conn_override=conn_override)

    # Protection: If incoming is empty and baseline exists, preserve baseline
    if not incoming_records and baseline_records:
        print("[EXPORTER] Incoming data is empty but baseline exists. Preserving known-good catalog.")
        incoming_records = baseline_records
    elif not incoming_records and not baseline_records and not allow_empty_if_no_baseline:
        print("[EXPORTER] Warning: No records found from database or baseline.")

    merged_records = merge_hackathon_records(baseline_records, incoming_records, as_of=as_of)
    payload = build_catalog_payload(merged_records, supplementary_links=supplementary_links)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write pattern: write to tmp file first, then os.replace
    tmp_path = output_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_path, output_path)

    # Also sync to frontend/public/data/hackathons.json if running standard export
    if output_path == DEFAULT_EXPORT_PATH and FRONTEND_EXPORT_PATH.parent.exists():
        FRONTEND_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        frontend_tmp = FRONTEND_EXPORT_PATH.with_suffix(".tmp")
        with open(frontend_tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(frontend_tmp, FRONTEND_EXPORT_PATH)

    print(f"[EXPORTER] Successfully exported {len(merged_records)} hackathons to {output_path}")
    return payload


if __name__ == "__main__":
    export_public_catalog()
