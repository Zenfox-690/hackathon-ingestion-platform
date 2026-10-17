import datetime
import hashlib
import json
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple

from db.migrations import apply_migrations
from filters.benefits import extract_special_benefits
from utils.dates import evaluate_hackathon_status
from utils.format import normalize_participation_format
from utils.urls import canonicalize_url

# Default module-level connection and cursor for backward-compatibility
conn = sqlite3.connect("hackathons.db", check_same_thread=False)
cursor = conn.cursor()

# Run migrations non-destructively on startup
apply_migrations(conn)


def generate_fingerprint(hackathon: Dict[str, Any]) -> str:
    link = hackathon.get("link") or ""
    canon_link = canonicalize_url(link) if link else ""

    if canon_link:
        raw = f"url:{canon_link.lower()}"
    else:
        deadline = hackathon.get("deadline") or ""
        if hasattr(deadline, "isoformat"):
            deadline = deadline.isoformat()
        name = (hackathon.get("name") or "").lower().strip()
        raw = f"name:{name}:{str(deadline).lower().strip()}"

    return hashlib.sha256(raw.encode()).hexdigest()


def _get_table_columns(cursor_target: Optional[sqlite3.Cursor] = None) -> set:
    c = cursor_target or cursor
    try:
        c.execute("PRAGMA table_info(hackathons)")
        return {row[1] for row in c.fetchall()}
    except Exception:
        return set()


def get_new_hackathons(
    hackathons: List[Dict[str, Any]], conn_override: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """
    Ingest hackathons into database with deduplication, URL canonicalization,
    legacy row compatibility, and non-destructive metadata persistence.
    Returns only newly inserted hackathons.
    """
    target_conn = conn_override or conn
    target_cursor = target_conn.cursor()
    new_items = []
    columns = _get_table_columns(target_cursor)
    has_metadata_cols = "description" in columns
    has_v3_cols = "reg_ends_at" in columns
    has_v4_cols = "benefits" in columns

    for hackathon in hackathons:
        raw_link = (hackathon.get("link") or "").strip()
        canon_link = canonicalize_url(raw_link) if raw_link else ""
        if canon_link:
            hackathon["link"] = canon_link

        fingerprint = hackathon.get("fingerprint") or generate_fingerprint(hackathon)
        name = (hackathon.get("name") or "").strip()
        deadline = hackathon.get("deadline")
        deadline_str = deadline.isoformat() if hasattr(deadline, "isoformat") else (str(deadline) if deadline else "")

        # Compute legacy fingerprint for backward-compatibility with older database rows
        legacy_raw = name.lower().strip() + deadline_str.lower().strip()
        legacy_fingerprint = hashlib.sha256(legacy_raw.encode()).hexdigest()

        # Check by canonical fingerprint, legacy fingerprint, or canonical/raw URL
        if canon_link:
            target_cursor.execute(
                """
                SELECT fingerprint FROM hackathons
                WHERE fingerprint = ?
                   OR fingerprint = ?
                   OR link = ?
                   OR link = ?
                   OR link = ?
                LIMIT 1
                """,
                (fingerprint, legacy_fingerprint, canon_link, canon_link + "/", raw_link),
            )
        else:
            target_cursor.execute(
                """
                SELECT fingerprint FROM hackathons
                WHERE fingerprint = ?
                   OR fingerprint = ?
                   OR (lower(name) = ? AND source = ?)
                LIMIT 1
                """,
                (fingerprint, legacy_fingerprint, name.lower().strip(), hackathon.get("source", "")),
            )

        existing_row = target_cursor.fetchone()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        reg_starts_at = hackathon.get("reg_starts_at") or ""
        reg_ends_at = hackathon.get("reg_ends_at") or ""
        starts_at = hackathon.get("starts_at") or ""
        ends_at = hackathon.get("ends_at") or ""
        source_status = hackathon.get("source_status") or ""
        is_section_link = 1 if hackathon.get("is_section_link") else 0
        loc = normalize_participation_format(hackathon.get("location"))
        hackathon["location"] = loc

        benefits = hackathon.get("benefits")
        if not benefits:
            benefits = extract_special_benefits(hackathon)
            hackathon["benefits"] = benefits
        benefits_json = json.dumps(benefits)

        if not existing_row:
            if has_v4_cols:
                desc = hackathon.get("description") or ""
                tags = json.dumps(hackathon.get("tags") or [])
                prize = hackathon.get("prize") or "Unknown"
                created_at = hackathon.get("created_at") or now_iso
                updated_at = hackathon.get("updated_at") or now_iso
                raw_data = json.dumps({k: v for k, v in hackathon.items() if k not in ("raw_data",)})

                target_cursor.execute(
                    """
                    INSERT INTO hackathons (
                        fingerprint, name, deadline, source, link,
                        description, tags, prize, location, created_at, updated_at, raw_data,
                        reg_starts_at, reg_ends_at, starts_at, ends_at, source_status, is_section_link,
                        benefits
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fingerprint,
                        name,
                        deadline,
                        hackathon.get("source", ""),
                        hackathon.get("link", ""),
                        desc,
                        tags,
                        prize,
                        loc,
                        created_at,
                        updated_at,
                        raw_data,
                        reg_starts_at,
                        reg_ends_at,
                        starts_at,
                        ends_at,
                        source_status,
                        is_section_link,
                        benefits_json,
                    ),
                )
            elif has_v3_cols:
                desc = hackathon.get("description") or ""
                tags = json.dumps(hackathon.get("tags") or [])
                prize = hackathon.get("prize") or "Unknown"
                created_at = hackathon.get("created_at") or now_iso
                updated_at = hackathon.get("updated_at") or now_iso
                raw_data = json.dumps({k: v for k, v in hackathon.items() if k not in ("raw_data",)})

                target_cursor.execute(
                    """
                    INSERT INTO hackathons (
                        fingerprint, name, deadline, source, link,
                        description, tags, prize, location, created_at, updated_at, raw_data,
                        reg_starts_at, reg_ends_at, starts_at, ends_at, source_status, is_section_link
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fingerprint,
                        name,
                        deadline,
                        hackathon.get("source", ""),
                        hackathon.get("link", ""),
                        desc,
                        tags,
                        prize,
                        loc,
                        created_at,
                        updated_at,
                        raw_data,
                        reg_starts_at,
                        reg_ends_at,
                        starts_at,
                        ends_at,
                        source_status,
                        is_section_link,
                    ),
                )
            elif has_metadata_cols:
                desc = hackathon.get("description") or ""
                tags = json.dumps(hackathon.get("tags") or [])
                prize = hackathon.get("prize") or "Unknown"
                loc = hackathon.get("location") or "Online"
                created_at = hackathon.get("created_at") or now_iso
                updated_at = hackathon.get("updated_at") or now_iso
                raw_data = json.dumps({k: v for k, v in hackathon.items() if k not in ("raw_data",)})

                target_cursor.execute(
                    """
                    INSERT INTO hackathons (
                        fingerprint, name, deadline, source, link,
                        description, tags, prize, location, created_at, updated_at, raw_data
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fingerprint,
                        name,
                        deadline,
                        hackathon.get("source", ""),
                        hackathon.get("link", ""),
                        desc,
                        tags,
                        prize,
                        loc,
                        created_at,
                        updated_at,
                        raw_data,
                    ),
                )
            else:
                target_cursor.execute(
                    """
                    INSERT INTO hackathons
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (fingerprint, name, deadline, hackathon.get("source", ""), hackathon.get("link", "")),
                )

            target_conn.commit()
            new_items.append(hackathon)
            safe_name = name.encode(getattr(sys.stdout, "encoding", "utf-8") or "utf-8", errors="replace").decode(
                getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
            )
            print(f"[NEW] {safe_name}")
        else:
            # Existing row: Non-destructively enrich missing metadata without wiping valid data
            existing_fp = existing_row[0]
            if has_metadata_cols:
                target_cursor.execute(
                    "SELECT description, prize, location FROM hackathons WHERE fingerprint = ?", (existing_fp,)
                )
                curr = target_cursor.fetchone()
                if curr:
                    curr_desc, curr_prize, curr_loc = curr
                    updates = []
                    params = []

                    new_desc = hackathon.get("description")
                    if new_desc and (not curr_desc or curr_desc.strip() == ""):
                        updates.append("description = ?")
                        params.append(new_desc)

                    new_prize = hackathon.get("prize")
                    if new_prize and new_prize != "Unknown" and (not curr_prize or curr_prize == "Unknown"):
                        updates.append("prize = ?")
                        params.append(new_prize)

                    new_loc = normalize_participation_format(hackathon.get("location"))
                    if (
                        new_loc
                        and new_loc != "Unknown"
                        and curr_loc in ("", "Unknown", "Online")
                        and new_loc != curr_loc
                    ):
                        updates.append("location = ?")
                        params.append(new_loc)

                    if has_v3_cols:
                        if reg_ends_at:
                            updates.append("reg_ends_at = ?")
                            params.append(reg_ends_at)
                        if reg_starts_at:
                            updates.append("reg_starts_at = ?")
                            params.append(reg_starts_at)
                        if starts_at:
                            updates.append("starts_at = ?")
                            params.append(starts_at)
                        if ends_at:
                            updates.append("ends_at = ?")
                            params.append(ends_at)
                        if source_status:
                            updates.append("source_status = ?")
                            params.append(source_status)

                    if has_v4_cols:
                        target_cursor.execute("SELECT benefits FROM hackathons WHERE fingerprint = ?", (existing_fp,))
                        b_row = target_cursor.fetchone()
                        if b_row and (not b_row[0] or b_row[0] == "[]") and benefits:
                            updates.append("benefits = ?")
                            params.append(benefits_json)

                    if updates:
                        updates.append("updated_at = ?")
                        params.append(now_iso)
                        params.append(existing_fp)
                        query = f"UPDATE hackathons SET {', '.join(updates)} WHERE fingerprint = ?"
                        target_cursor.execute(query, tuple(params))
                        target_conn.commit()

    return new_items


def add_user(chat_id: Any) -> None:
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?)", (str(chat_id),))
    conn.commit()


def add_filter(chat_id: Any, keyword: str) -> None:
    cursor.execute(
        """
        INSERT INTO filters
        (chat_id, keyword)
        VALUES (?, ?)
        """,
        (str(chat_id), keyword.lower()),
    )
    conn.commit()


def get_filters(chat_id: Any) -> List[str]:
    cursor.execute(
        """
        SELECT keyword
        FROM filters
        WHERE chat_id = ?
        """,
        (str(chat_id),),
    )
    rows = cursor.fetchall()
    return [row[0] for row in rows]


def remove_filter(chat_id: Any, keyword: str) -> None:
    cursor.execute(
        """
        DELETE FROM filters
        WHERE chat_id = ?
        AND keyword = ?
        """,
        (str(chat_id), keyword.lower()),
    )
    conn.commit()


def clear_filters(chat_id: Any) -> None:
    cursor.execute(
        """
        DELETE FROM filters
        WHERE chat_id = ?
        """,
        (str(chat_id),),
    )
    conn.commit()


def get_users() -> List[str]:
    cursor.execute("SELECT chat_id FROM users")
    rows = cursor.fetchall()
    return [row[0] for row in rows]


def get_upcoming(limit: int = 5) -> List[Tuple]:
    cursor.execute(
        """
        SELECT name, deadline, source, link
        FROM hackathons
        WHERE deadline IS NOT NULL
          AND deadline != ''
          AND lower(deadline) != 'unknown'
        ORDER BY deadline ASC
        LIMIT ?
        """,
        (limit,),
    )
    return cursor.fetchall()


def already_notified(chat_id: Any, fingerprint: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM notified
        WHERE chat_id = ?
        AND fingerprint = ?
        """,
        (str(chat_id), fingerprint),
    )
    return cursor.fetchone() is not None


def mark_notified(chat_id: Any, fingerprint: str) -> None:
    cursor.execute(
        """
        INSERT OR IGNORE INTO notified
        VALUES (?, ?)
        """,
        (str(chat_id), fingerprint),
    )
    conn.commit()


def get_stats() -> Dict[str, int]:
    cursor.execute("SELECT COUNT(*) FROM hackathons")
    hackathons = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM filters")
    filters = cursor.fetchone()[0]

    return {"hackathons": hackathons, "users": users, "filters": filters}


def search_hackathons(query: str) -> List[Tuple]:
    cursor.execute(
        """
        SELECT name, deadline, source, link
        FROM hackathons
        WHERE lower(name)
        LIKE ?
        LIMIT 10
        """,
        (f"%{query.lower()}%",),
    )
    return cursor.fetchall()


def get_hackathon_by_id(fingerprint: str) -> Optional[Dict[str, Any]]:
    """Fetch a single hackathon record by fingerprint."""
    columns = _get_table_columns()
    has_meta = "description" in columns
    has_v3 = "reg_ends_at" in columns

    if has_v3:
        cursor.execute(
            """
            SELECT fingerprint, name, deadline, source, link,
                   description, tags, prize, location, created_at, updated_at,
                   reg_starts_at, reg_ends_at, starts_at, ends_at, source_status, is_section_link
            FROM hackathons
            WHERE fingerprint = ?
            """,
            (fingerprint,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        tags = []
        try:
            tags = json.loads(row[6]) if row[6] else []
        except Exception:
            pass

        st = evaluate_hackathon_status(
            deadline=row[2],
            reg_starts_at=row[11],
            reg_ends_at=row[12],
            starts_at=row[13],
            ends_at=row[14],
            source_status=row[15],
        )

        return {
            "fingerprint": row[0],
            "id": row[0],
            "name": row[1],
            "title": row[1],
            "deadline": row[2] or "Unknown",
            "source": row[3],
            "link": row[4],
            "url": row[4],
            "description": row[5] or "",
            "tags": tags,
            "prize": row[7] or "Unknown",
            "location": row[8] or "Online",
            "created_at": row[9] or "",
            "updated_at": row[10] or "",
            "reg_starts_at": row[11] or "",
            "reg_ends_at": row[12] or "",
            "starts_at": row[13] or "",
            "ends_at": row[14] or "",
            "source_status": row[15] or "",
            "is_section_link": bool(row[16]),
            "status": st,
        }
    elif has_meta:
        cursor.execute(
            """
            SELECT fingerprint, name, deadline, source, link,
                   description, tags, prize, location, created_at, updated_at
            FROM hackathons
            WHERE fingerprint = ?
            """,
            (fingerprint,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        tags = []
        try:
            tags = json.loads(row[6]) if row[6] else []
        except Exception:
            pass

        st = evaluate_hackathon_status(deadline=row[2])

        return {
            "fingerprint": row[0],
            "id": row[0],
            "name": row[1],
            "title": row[1],
            "deadline": row[2] or "Unknown",
            "source": row[3],
            "link": row[4],
            "url": row[4],
            "description": row[5] or "",
            "tags": tags,
            "prize": row[7] or "Unknown",
            "location": row[8] or "Online",
            "created_at": row[9] or "",
            "updated_at": row[10] or "",
            "is_section_link": False,
            "status": st,
        }
    else:
        cursor.execute(
            "SELECT fingerprint, name, deadline, source, link FROM hackathons WHERE fingerprint = ?", (fingerprint,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        st = evaluate_hackathon_status(deadline=row[2])
        return {
            "fingerprint": row[0],
            "id": row[0],
            "name": row[1],
            "title": row[1],
            "deadline": row[2] or "Unknown",
            "source": row[3],
            "link": row[4],
            "url": row[4],
            "description": "",
            "tags": [],
            "prize": "Unknown",
            "location": "Online",
            "created_at": "",
            "updated_at": "",
            "is_section_link": False,
            "status": st,
        }


def get_all_public_hackathons(
    include_sections: bool = False, conn_override: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """
    Returns public hackathon catalogue records.
    By default excludes section navigation links so that only real hackathons are returned.
    Recalculates status dynamically so stale dates are never falsely presented as open.
    """
    target_conn = conn_override or conn
    target_cursor = target_conn.cursor()

    columns = _get_table_columns(target_cursor)
    has_meta = "description" in columns
    has_v3 = "is_section_link" in columns
    has_v4 = "benefits" in columns

    where_clause = ""
    if has_v3 and not include_sections:
        where_clause = "WHERE is_section_link = 0 OR is_section_link IS NULL"

    if has_v4:
        target_cursor.execute(
            f"""
            SELECT fingerprint, name, deadline, source, link,
                   description, tags, prize, location, created_at, updated_at,
                   reg_starts_at, reg_ends_at, starts_at, ends_at, source_status, is_section_link,
                   benefits
            FROM hackathons
            {where_clause}
            ORDER BY created_at DESC, deadline ASC
            """
        )
        rows = target_cursor.fetchall()
        result = []
        for r in rows:
            tags = []
            try:
                tags = json.loads(r[6]) if r[6] else []
            except Exception:
                pass

            st = evaluate_hackathon_status(
                deadline=r[2],
                reg_starts_at=r[11],
                reg_ends_at=r[12],
                starts_at=r[13],
                ends_at=r[14],
                source_status=r[15],
            )

            b_list = []
            try:
                if len(r) > 17 and r[17]:
                    b_list = json.loads(r[17])
            except Exception:
                b_list = []

            if not b_list:
                b_list = extract_special_benefits(
                    {
                        "fingerprint": r[0],
                        "name": r[1],
                        "description": r[5] or "",
                        "tags": tags,
                        "prize": r[7] or "Unknown",
                        "link": r[4],
                    }
                )

            loc = normalize_participation_format(r[8])

            result.append(
                {
                    "fingerprint": r[0],
                    "id": r[0],
                    "name": r[1],
                    "title": r[1],
                    "deadline": r[2] or "Unknown",
                    "source": r[3],
                    "link": r[4],
                    "url": r[4],
                    "description": r[5] or "",
                    "tags": tags,
                    "prize": r[7] or "Unknown",
                    "location": loc,
                    "benefits": b_list,
                    "created_at": r[9] or "",
                    "updated_at": r[10] or "",
                    "reg_starts_at": r[11] or "",
                    "reg_ends_at": r[12] or "",
                    "starts_at": r[13] or "",
                    "ends_at": r[14] or "",
                    "source_status": r[15] or "",
                    "is_section_link": bool(r[16]),
                    "status": st,
                }
            )
        return result
    elif has_v3:
        target_cursor.execute(
            f"""
            SELECT fingerprint, name, deadline, source, link,
                   description, tags, prize, location, created_at, updated_at,
                   reg_starts_at, reg_ends_at, starts_at, ends_at, source_status, is_section_link
            FROM hackathons
            {where_clause}
            ORDER BY created_at DESC, deadline ASC
            """
        )
        rows = target_cursor.fetchall()
        result = []
        for r in rows:
            tags = []
            try:
                tags = json.loads(r[6]) if r[6] else []
            except Exception:
                pass

            st = evaluate_hackathon_status(
                deadline=r[2],
                reg_starts_at=r[11],
                reg_ends_at=r[12],
                starts_at=r[13],
                ends_at=r[14],
                source_status=r[15],
            )

            b_list = extract_special_benefits(
                {
                    "fingerprint": r[0],
                    "name": r[1],
                    "description": r[5] or "",
                    "tags": tags,
                    "prize": r[7] or "Unknown",
                    "link": r[4],
                }
            )
            loc = normalize_participation_format(r[8])

            result.append(
                {
                    "fingerprint": r[0],
                    "id": r[0],
                    "name": r[1],
                    "title": r[1],
                    "deadline": r[2] or "Unknown",
                    "source": r[3],
                    "link": r[4],
                    "url": r[4],
                    "description": r[5] or "",
                    "tags": tags,
                    "prize": r[7] or "Unknown",
                    "location": loc,
                    "benefits": b_list,
                    "created_at": r[9] or "",
                    "updated_at": r[10] or "",
                    "reg_starts_at": r[11] or "",
                    "reg_ends_at": r[12] or "",
                    "starts_at": r[13] or "",
                    "ends_at": r[14] or "",
                    "source_status": r[15] or "",
                    "is_section_link": bool(r[16]),
                    "status": st,
                }
            )
        return result
    elif has_meta:
        target_cursor.execute(
            """
            SELECT fingerprint, name, deadline, source, link,
                   description, tags, prize, location, created_at, updated_at
            FROM hackathons
            ORDER BY created_at DESC, deadline ASC
            """
        )
        rows = target_cursor.fetchall()
        result = []
        for r in rows:
            tags = []
            try:
                tags = json.loads(r[6]) if r[6] else []
            except Exception:
                pass
            st = evaluate_hackathon_status(deadline=r[2])
            result.append(
                {
                    "fingerprint": r[0],
                    "id": r[0],
                    "name": r[1],
                    "title": r[1],
                    "deadline": r[2] or "Unknown",
                    "source": r[3],
                    "link": r[4],
                    "url": r[4],
                    "description": r[5] or "",
                    "tags": tags,
                    "prize": r[7] or "Unknown",
                    "location": r[8] or "Online",
                    "created_at": r[9] or "",
                    "updated_at": r[10] or "",
                    "is_section_link": False,
                    "status": st,
                }
            )
        return result
    else:
        target_cursor.execute("SELECT fingerprint, name, deadline, source, link FROM hackathons")
        rows = target_cursor.fetchall()
        return [
            {
                "fingerprint": r[0],
                "id": r[0],
                "name": r[1],
                "title": r[1],
                "deadline": r[2] or "Unknown",
                "source": r[3],
                "link": r[4],
                "url": r[4],
                "description": "",
                "tags": [],
                "prize": "Unknown",
                "location": "Online",
                "created_at": "",
                "updated_at": "",
                "is_section_link": False,
                "status": evaluate_hackathon_status(deadline=r[2]),
            }
            for r in rows
        ]


def get_supplementary_links(conn_override: Optional[sqlite3.Connection] = None) -> List[Dict[str, str]]:
    """Returns supplementary navigation portal links (e.g., Devfolio section links)."""
    target_conn = conn_override or conn
    target_cursor = target_conn.cursor()

    columns = _get_table_columns(target_cursor)
    if "is_section_link" in columns:
        target_cursor.execute(
            """
            SELECT name, link, source
            FROM hackathons
            WHERE is_section_link = 1
            ORDER BY name ASC
            """
        )
        return [{"name": r[0], "url": r[1], "source": r[2]} for r in target_cursor.fetchall()]
    return []
