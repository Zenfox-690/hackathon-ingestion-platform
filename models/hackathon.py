import datetime
import hashlib
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from utils.dates import evaluate_hackathon_status, normalize_date
from utils.urls import canonicalize_url


class HackathonStatus(str, Enum):
    OPEN = "open"
    UPCOMING = "upcoming"
    ENDED = "ended"
    UNKNOWN = "unknown"


class Hackathon(BaseModel):
    """Canonical Hackathon Data Model with validation, normalization, and stable identity."""

    fingerprint: str = Field(default="", description="Unique SHA-256 fingerprint")
    name: str = Field(..., min_length=1, description="Official hackathon name/title")
    link: str = Field(..., description="Canonical URL to the hackathon page")
    source: str = Field(..., description="Origin platform, e.g., Devpost, Devfolio, Unstop")
    deadline: Optional[str] = Field(default=None, description="Normalized ISO 8601 deadline or None")
    reg_starts_at: Optional[str] = Field(default=None, description="Registration start timestamp")
    reg_ends_at: Optional[str] = Field(default=None, description="Registration deadline timestamp")
    starts_at: Optional[str] = Field(default=None, description="Event start timestamp")
    ends_at: Optional[str] = Field(default=None, description="Event end timestamp")
    source_status: Optional[str] = Field(
        default=None, description="Platform reported status hint (open, upcoming, ended)"
    )
    is_section_link: bool = Field(
        default=False, description="Flag indicating if this record is a portal/section navigation link"
    )
    description: Optional[str] = Field(default="", description="Summary or description")
    tags: List[str] = Field(default_factory=list, description="Associated skill/topic tags")
    prize: Optional[str] = Field(default="Unknown", description="Prize amount or summary")
    location: Optional[str] = Field(default="Online", description="Online or physical location")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp when first discovered")
    updated_at: Optional[str] = Field(default=None, description="ISO timestamp of last update")

    @property
    def title(self) -> str:
        """Alias for name for consumer convenience."""
        return self.name

    @property
    def url(self) -> str:
        """Alias for link for consumer convenience."""
        return self.link

    @property
    def id(self) -> str:
        """Alias for fingerprint for REST API ID access."""
        return self.fingerprint

    @property
    def status(self) -> HackathonStatus:
        """Compute status dynamically based on current UTC time vs verified dates."""
        st = evaluate_hackathon_status(
            deadline=self.deadline,
            reg_starts_at=self.reg_starts_at,
            reg_ends_at=self.reg_ends_at,
            starts_at=self.starts_at,
            ends_at=self.ends_at,
            source_status=self.source_status,
        )
        return HackathonStatus(st)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, v: Any) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Hackathon name must be a non-empty string")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Hackathon name cannot be blank")
        return cleaned

    @field_validator("link", mode="before")
    @classmethod
    def normalize_link(cls, v: Any) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Hackathon link must be a non-empty URL string")
        canon = canonicalize_url(v.strip())
        if not canon:
            canon = v.strip()
        return canon

    @field_validator("deadline", mode="before")
    @classmethod
    def clean_deadline(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if hasattr(v, "isoformat"):
            return v.isoformat()
        if isinstance(v, str):
            cleaned = v.strip()
            if not cleaned or cleaned.lower() == "unknown":
                return None
            norm = normalize_date(cleaned)
            return norm if norm else cleaned
        return None

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v: Any) -> List[str]:
        if not v:
            return []
        if isinstance(v, str):
            parts = [t.strip().lower() for t in v.split(",") if t.strip()]
            return sorted(list(set(parts)))
        if isinstance(v, (list, set, tuple)):
            clean_list = [str(t).strip().lower() for t in v if str(t).strip()]
            return sorted(list(set(clean_list)))
        return []

    @field_validator("prize", mode="before")
    @classmethod
    def clean_prize(cls, v: Any) -> str:
        if not v or not str(v).strip():
            return "Unknown"
        return str(v).strip()

    @field_validator("location", mode="before")
    @classmethod
    def clean_location(cls, v: Any) -> str:
        if not v or not str(v).strip():
            return "Online"
        return str(v).strip()

    @model_validator(mode="after")
    def compute_fields(self) -> "Hackathon":
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now_iso
        if not self.updated_at:
            self.updated_at = now_iso

        # Stable fingerprint computation matching Phase 1 URL-priority logic
        if not self.fingerprint:
            if self.link:
                raw = f"url:{self.link.lower()}"
            else:
                dl = self.deadline or ""
                raw = f"name:{self.name.lower().strip()}:{str(dl).lower().strip()}"
            self.fingerprint = hashlib.sha256(raw.encode()).hexdigest()

        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert to standard dictionary matching consumer expectations."""
        return {
            "fingerprint": self.fingerprint,
            "id": self.fingerprint,
            "name": self.name,
            "title": self.name,
            "link": self.link,
            "url": self.link,
            "source": self.source,
            "deadline": self.deadline or "Unknown",
            "reg_starts_at": self.reg_starts_at,
            "reg_ends_at": self.reg_ends_at,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
            "source_status": self.source_status,
            "is_section_link": self.is_section_link,
            "description": self.description or "",
            "tags": self.tags,
            "prize": self.prize,
            "location": self.location,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SupplementaryLink(BaseModel):
    name: str
    url: str
    source: str


class CatalogMetadata(BaseModel):
    version: str = "1.0.0"
    generated_at: str
    total_count: int
    active_count: int
    open_count: int = 0
    upcoming_count: int = 0
    ended_count: int = 0
    sources: Dict[str, int] = Field(default_factory=dict)
    supplementary_links: List[SupplementaryLink] = Field(default_factory=list)


class HackathonCatalog(BaseModel):
    metadata: CatalogMetadata
    hackathons: List[Hackathon]
