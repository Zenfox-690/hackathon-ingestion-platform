import argparse
import datetime
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import db.store as store
from utils.dates import evaluate_hackathon_status, normalize_date
from utils.format import normalize_participation_format
from utils.urls import canonicalize_url

DEFAULT_EXPORT_PATH = Path("data/hackathons.json")
FRONTEND_EXPORT_PATH = Path("frontend/public/data/hackathons.json")
FRONTEND_ALT_EXPORT_PATH = Path("frontend/public/hackathons.json")

ALLOWED_SOURCES = {"Devpost", "Devfolio", "Unstop"}
ALLOWED_STATUSES = {"open", "upcoming", "ended", "unknown"}
ALLOWED_FORMATS = {"Online", "In-Person", "Hybrid", "Unknown"}

KNOWN_SECTION_NAMES = {
    "your hackathons",
    "all upcoming hackathons",
    "all past hackathons",
    "all open hackathons",
    "all opening hackathons",
}


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


def is_test_fixture_item(item: Dict[str, Any]) -> bool:
    src = (item.get("source") or "").strip()
    name = (item.get("name") or item.get("title") or "").strip().lower()
    if src in ("MockSuccessSource", "MockFailingSource", "MockPollutionSource"):
        return True
    if "reliable ai hackathon" in name or "pollution canary" in name or "mock" in src.lower():
        return True
    return False


def get_canonical_record_key(item: Dict[str, Any]) -> str:
    raw_link = (item.get("link") or item.get("url") or "").strip()
    canon_link = canonicalize_url(raw_link) if raw_link else ""
    if canon_link:
        return f"link:{canon_link.lower()}"
    name = (item.get("name") or item.get("title") or "").strip().lower()
    source = (item.get("source") or "").strip().lower()
    return f"name:{source}:{name}"


def merge_hackathon_records(
    baseline_records: List[Dict[str, Any]],
    incoming_records: List[Dict[str, Any]],
    as_of: Optional[datetime.datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Merge incoming validated records with baseline records.
    - Uses canonicalized link as identity key so deadline changes/fingerprint shifts update the same event.
    - Excludes test fixtures and section navigation links.
    - Allows newer, valid source data to update mutable fields (deadline extensions, prizes, etc.).
    - Never overwrites good existing values with empty or malformed values.
    - Clears stale benefits when fresh source scrape establishes no benefits remain.
    - Re-evaluates status strictly against reference time.
    """
    by_identity: Dict[str, Dict[str, Any]] = {}
    fingerprint_to_key: Dict[str, str] = {}

    # Seed baseline records (excluding fixtures and navigation links)
    for item in baseline_records:
        if is_section_link_item(item) or is_test_fixture_item(item):
            continue
        key = get_canonical_record_key(item)
        if not key:
            continue
        by_identity[key] = dict(item)
        fp = item.get("fingerprint") or item.get("id")
        if fp:
            fingerprint_to_key[fp] = key

    # Merge incoming records
    for inc in incoming_records:
        if is_section_link_item(inc) or is_test_fixture_item(inc):
            continue
        key = get_canonical_record_key(inc)
        fp = inc.get("fingerprint") or inc.get("id")

        target_key = key
        if key not in by_identity and fp and fp in fingerprint_to_key:
            target_key = fingerprint_to_key[fp]

        if target_key in by_identity:
            curr = by_identity[target_key]
            merged = dict(curr)

            # Name update: accept valid single-line incoming title
            inc_name = (inc.get("name") or inc.get("title") or "").strip()
            if inc_name and inc_name not in ("Unknown", "") and "\n" not in inc_name:
                merged["name"] = inc_name
                merged["title"] = inc_name

            # Updatable fields: allow newer valid incoming data to update stale records
            for field in (
                "deadline",
                "reg_starts_at",
                "reg_ends_at",
                "starts_at",
                "ends_at",
                "source_status",
                "prize",
                "description",
                "location",
            ):
                inc_val = inc.get(field)
                if inc_val is not None:
                    str_inc = str(inc_val).strip()
                    if str_inc and str_inc.lower() not in ("unknown", ""):
                        merged[field] = inc_val

            # Tags: deduplicate
            merged_tags = sorted(list(set((curr.get("tags") or []) + (inc.get("tags") or []))))
            merged["tags"] = merged_tags

            # Benefits: If fresh incoming scrape provides benefits, replace old benefits
            # (prevents retaining stale benefits indefinitely)
            if "benefits" in inc:
                merged["benefits"] = inc["benefits"]
            elif "benefits" in curr:
                merged["benefits"] = curr["benefits"]
            else:
                merged["benefits"] = []

            # Timestamp update
            merged["updated_at"] = inc.get("updated_at") or datetime.datetime.now(datetime.timezone.utc).isoformat()
            by_identity[target_key] = merged
        else:
            by_identity[key] = dict(inc)
            if fp:
                fingerprint_to_key[fp] = key

    final_records = []
    for item in by_identity.values():
        clean_item = dict(item)

        # Normalize URL
        raw_link = clean_item.get("link") or clean_item.get("url") or ""
        canon_link = canonicalize_url(raw_link) if raw_link else ""
        clean_item["link"] = canon_link
        clean_item["url"] = canon_link

        # Clean title: single line, no badges/newlines
        raw_title = clean_item.get("name") or clean_item.get("title") or ""
        clean_title = raw_title.splitlines()[0].strip() if raw_title else "Unknown"
        clean_item["name"] = clean_title
        clean_item["title"] = clean_title

        fp = clean_item.get("fingerprint") or clean_item.get("id") or ""
        clean_item["fingerprint"] = fp
        clean_item["id"] = fp
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
    seen_links = set()

    for r in records:
        if is_section_link_item(r) or is_test_fixture_item(r):
            continue

        link = r.get("link") or r.get("url") or ""
        if link in seen_links:
            continue
        seen_links.add(link)

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

        clean_name = (r.get("name") or r.get("title") or "").splitlines()[0].strip()

        sanitized = {
            "id": r.get("id") or r.get("fingerprint"),
            "fingerprint": r.get("fingerprint") or r.get("id"),
            "name": clean_name,
            "title": clean_name,
            "link": link,
            "url": link,
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


def validate_catalog_payload(payload: Dict[str, Any]) -> List[str]:
    """
    Deterministic validation check for public catalogue payload:
    - Required metadata fields
    - Allowed source names (Devpost, Devfolio, Unstop)
    - Zero test fixtures
    - Unique canonical links
    - Single-line titles without newlines
    - Valid status and participation format tokens
    """
    errors: List[str] = []
    if not isinstance(payload, dict):
        return ["Payload is not a valid JSON dictionary"]

    meta = payload.get("metadata")
    if not isinstance(meta, dict):
        errors.append("Missing metadata dictionary")
    else:
        for rf in ("version", "generated_at", "total_count", "sources", "formats"):
            if rf not in meta:
                errors.append(f"Metadata missing required field: {rf}")
        sources = meta.get("sources", {})
        for src in sources.keys():
            if src not in ALLOWED_SOURCES:
                errors.append(f"Forbidden source in metadata sources: {src}")

    hackathons = payload.get("hackathons")
    if not isinstance(hackathons, list):
        errors.append("Missing or invalid hackathons list")
        return errors

    seen_links = set()
    for idx, h in enumerate(hackathons):
        h_id = h.get("id") or h.get("fingerprint") or f"index_{idx}"
        name = h.get("name") or h.get("title") or ""
        link = h.get("link") or h.get("url") or ""
        src = h.get("source") or ""

        if not h_id:
            errors.append(f"Record {idx} missing ID")
        if not name or not name.strip():
            errors.append(f"Record {h_id} missing name")
        elif "\n" in name or "\r" in name:
            errors.append(f"Record {h_id} contains multiline title: {repr(name)}")

        if is_test_fixture_item(h):
            errors.append(f"Record {h_id} contains test fixture: {src} / {name}")

        if src not in ALLOWED_SOURCES:
            errors.append(f"Record {h_id} has disallowed source: {src}")

        if not link or not (link.startswith("http://") or link.startswith("https://")):
            errors.append(f"Record {h_id} has invalid link: {link}")
        elif link in seen_links:
            errors.append(f"Duplicate canonical link detected: {link}")
        else:
            seen_links.add(link)

        st = h.get("status")
        if st not in ALLOWED_STATUSES:
            errors.append(f"Record {h_id} has invalid status: {st}")

        loc = h.get("location")
        if loc not in ALLOWED_FORMATS:
            errors.append(f"Record {h_id} has invalid format/location: {loc}")

    return errors


def validate_catalog_file(catalog_path: Path = DEFAULT_EXPORT_PATH) -> bool:
    """Validate candidate catalog file on disk."""
    if not catalog_path.exists():
        print(f"[VALIDATE] ERROR: Catalog file {catalog_path} does not exist.")
        return False
    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        errors = validate_catalog_payload(data)
        if errors:
            print(f"[VALIDATE] Catalog validation FAILED with {len(errors)} error(s):")
            for err in errors[:10]:
                print(f"  • {err}")
            return False
        print(f"[VALIDATE] Catalog {catalog_path} PASSED validation ({data['metadata']['total_count']} records).")
        return True
    except Exception as e:
        print(f"[VALIDATE] Failed to load/validate {catalog_path}: {e}")
        return False


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
    Validates candidate payload before persisting.
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

    # Deterministic validation check before persistence
    errors = validate_catalog_payload(payload)
    if errors:
        raise ValueError(f"Catalog payload failed validation ({len(errors)} errors): {errors[:5]}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write pattern: write to tmp file first, then os.replace
    tmp_path = output_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, output_path)

    # Sync to frontend static paths only when publishing the production catalog
    if output_path.resolve() == DEFAULT_EXPORT_PATH.resolve():
        for fe_path in (FRONTEND_EXPORT_PATH, FRONTEND_ALT_EXPORT_PATH):
            if fe_path.parent.exists():
                fe_path.parent.mkdir(parents=True, exist_ok=True)
                fe_tmp = fe_path.with_suffix(".tmp")
                with open(fe_tmp, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(fe_tmp, fe_path)

    print(f"[EXPORTER] Successfully exported and validated {len(payload['hackathons'])} hackathons to {output_path}")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hackathon Ingestion Catalog Exporter")
    parser.add_argument("--validate", action="store_true", help="Validate catalog on disk without exporting")
    parser.add_argument("--path", type=str, default=str(DEFAULT_EXPORT_PATH), help="Catalog path")
    args = parser.parse_args()

    if args.validate:
        valid = validate_catalog_file(Path(args.path))
        sys.exit(0 if valid else 1)
    else:
        export_public_catalog()
