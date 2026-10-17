import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from api.adapter import HackathonDataAdapter
from api.schemas import HackathonItem, HackathonListResponse, HealthResponse, StatsResponse

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse, summary="Service health check")
def health_check():
    """Returns service health status, database connectivity, and record counts."""
    stats = HackathonDataAdapter.get_stats()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return HealthResponse(
        status="ok",
        timestamp=now_iso,
        version="1.0.0",
        database_connected=True,
        total_hackathons=stats["total_hackathons"],
        active_hackathons=stats["status_counts"].get("open", 0) + stats["status_counts"].get("upcoming", 0),
    )


@router.get("/stats", response_model=StatsResponse, summary="Hackathon platform statistics")
def get_stats():
    """Returns platform summary metrics grouped by platform source and active status."""
    return HackathonDataAdapter.get_stats()


@router.get("/hackathons", response_model=HackathonListResponse, summary="List and filter hackathons")
def list_hackathons(
    q: Optional[str] = Query(None, description="Free text search on title or description"),
    source: Optional[str] = Query(None, description="Filter by platform source (e.g. Devpost, Devfolio, Unstop)"),
    tag: Optional[str] = Query(None, description="Filter by category or topic tag"),
    status: Optional[str] = Query(
        None, pattern="^(actionable|open|upcoming|ended|past|unknown)$", description="Filter by event status"
    ),
    sort_by: str = Query("deadline", pattern="^(deadline|name|created_at|source)$", description="Field to sort by"),
    order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
):
    """
    Search and filter public hackathons with bounded pagination and predictable schemas.
    Excludes all private bot state, user chat IDs, and credentials.
    """
    total, total_pages, items = HackathonDataAdapter.query(
        q=q, source=source, tag=tag, status=status, sort_by=sort_by, sort_order=order, page=page, limit=limit
    )

    return HackathonListResponse(
        total=total, page=page, limit=limit, total_pages=total_pages, items=[HackathonItem(**item) for item in items]
    )


@router.get("/hackathons/{hackathon_id}", response_model=HackathonItem, summary="Get hackathon by fingerprint ID")
def get_hackathon(hackathon_id: str):
    """Retrieve details for a single hackathon by its stable SHA-256 fingerprint ID."""
    item = HackathonDataAdapter.get_by_id(hackathon_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Hackathon with ID '{hackathon_id}' not found"
        )
    return HackathonItem(**item)
