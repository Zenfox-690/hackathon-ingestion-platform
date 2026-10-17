import math
from typing import Any, Dict, List, Optional, Tuple

import db.store as store
from utils.dates import evaluate_hackathon_status, normalize_date


class HackathonDataAdapter:
    """Read-only data adapter for FastAPI backend with robust filtering, search, and pagination."""

    @staticmethod
    def get_all(include_sections: bool = False) -> List[Dict[str, Any]]:
        records = store.get_all_public_hackathons(include_sections=include_sections)
        for r in records:
            r["status"] = evaluate_hackathon_status(
                deadline=r.get("deadline"),
                reg_starts_at=r.get("reg_starts_at"),
                reg_ends_at=r.get("reg_ends_at"),
                starts_at=r.get("starts_at"),
                ends_at=r.get("ends_at"),
                source_status=r.get("source_status"),
            )
        return records

    @classmethod
    def get_by_id(cls, hackathon_id: str) -> Optional[Dict[str, Any]]:
        rec = store.get_hackathon_by_id(hackathon_id)
        if rec:
            rec["status"] = evaluate_hackathon_status(
                deadline=rec.get("deadline"),
                reg_starts_at=rec.get("reg_starts_at"),
                reg_ends_at=rec.get("reg_ends_at"),
                starts_at=rec.get("starts_at"),
                ends_at=rec.get("ends_at"),
                source_status=rec.get("source_status"),
            )
        return rec

    @classmethod
    def query(
        cls,
        q: Optional[str] = None,
        source: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None,
        sort_by: str = "deadline",
        sort_order: str = "asc",
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[int, int, List[Dict[str, Any]]]:
        all_records = cls.get_all(include_sections=False)
        filtered = []

        q_clean = q.strip().lower() if q else None
        src_clean = source.strip().lower() if source else None
        tag_clean = tag.strip().lower() if tag else None
        status_clean = status.strip().lower() if status else None

        for item in all_records:
            # Skip section links
            if item.get("is_section_link"):
                continue

            # Text search filter
            if q_clean:
                title_match = q_clean in (item.get("name") or "").lower()
                desc_match = q_clean in (item.get("description") or "").lower()
                tag_match = any(q_clean in str(t).lower() for t in (item.get("tags") or []))
                if not (title_match or desc_match or tag_match):
                    continue

            # Source filter
            if src_clean:
                if (item.get("source") or "").lower() != src_clean:
                    continue

            # Tag filter
            if tag_clean:
                item_tags = [str(t).lower() for t in (item.get("tags") or [])]
                if tag_clean not in item_tags:
                    continue

            # Status filter
            if status_clean:
                item_status = item.get("status", "unknown").lower()
                if status_clean == "actionable":
                    if item_status not in ("open", "upcoming"):
                        continue
                elif status_clean in ("ended", "past"):
                    if item_status != "ended":
                        continue
                else:
                    if item_status != status_clean:
                        continue

            filtered.append(item)

        # Sorting
        reverse = sort_order.lower() == "desc"
        if sort_by in ("name", "title"):
            filtered.sort(key=lambda x: (x.get("name") or "").lower(), reverse=reverse)
        elif sort_by == "created_at":
            filtered.sort(key=lambda x: x.get("created_at") or "", reverse=reverse)
        elif sort_by == "source":
            filtered.sort(key=lambda x: (x.get("source") or "").lower(), reverse=reverse)
        else:
            # Default: Actionable first, then soonest deadline
            def dl_sort_key(x):
                st = x.get("status", "unknown")
                priority = {"open": 0, "upcoming": 1, "unknown": 2, "ended": 3}.get(st, 2)
                dl = x.get("deadline") or ""
                norm = normalize_date(dl) or (dl if "T" in dl else "9999-99-99")
                return (priority, norm)

            filtered.sort(key=dl_sort_key, reverse=reverse)

        total = len(filtered)
        total_pages = math.ceil(total / limit) if total > 0 else 1

        # Pagination slice
        offset = (page - 1) * limit
        items = filtered[offset : offset + limit]

        return total, total_pages, items

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        all_records = cls.get_all(include_sections=False)
        sources: Dict[str, int] = {}
        status_counts: Dict[str, int] = {"open": 0, "upcoming": 0, "ended": 0, "unknown": 0}

        for item in all_records:
            s = item.get("source", "Unknown")
            sources[s] = sources.get(s, 0) + 1
            st = item.get("status", "unknown")
            status_counts[st] = status_counts.get(st, 0) + 1

        supplementary = store.get_supplementary_links()

        return {
            "total_hackathons": len(all_records),
            "sources": sources,
            "status_counts": status_counts,
            "active_hackathons": status_counts["open"] + status_counts["upcoming"],
            "supplementary_links": supplementary,
        }
