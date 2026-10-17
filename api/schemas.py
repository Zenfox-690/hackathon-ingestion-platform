from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SpecialBenefitItem(BaseModel):
    name: str = Field(..., description="Benefit or provider name")
    category: str = Field(..., description="Category (e.g. cloud_credits, api_credits, dev_tools, startup_perks)")
    description: str = Field(default="", description="Benefit description or credit amount")
    requires_separate_application: bool = Field(default=False, description="Whether a separate application is needed")
    application_deadline: Optional[str] = Field(
        default=None, description="Benefit application deadline if explicitly stated"
    )
    application_url: Optional[str] = Field(default=None, description="Direct URL to apply for benefit")
    source_url: Optional[str] = Field(default=None, description="Official evidence or documentation URL")
    eligibility: Optional[str] = Field(default=None, description="Eligibility criteria if stated")
    confidence: str = Field(default="verified", description="'verified' or 'unverified'")


class HackathonItem(BaseModel):
    id: str = Field(..., description="Stable SHA-256 fingerprint ID")
    fingerprint: str
    name: str = Field(..., description="Hackathon title")
    title: str
    link: str = Field(..., description="Canonical URL to registration/details")
    url: str
    source: str = Field(..., description="Source platform name")
    deadline: Optional[str] = Field(default="Unknown", description="Deadline date string or ISO timestamp")
    description: Optional[str] = Field(default="", description="Description or host")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    prize: Optional[str] = Field(default="Unknown", description="Prize pool information")
    location: Optional[str] = Field(default="Online", description="Online or physical venue")
    status: str = Field(default="unknown", description="open, upcoming, ended, or unknown")
    benefits: List[SpecialBenefitItem] = Field(default_factory=list, description="Special sponsor benefits and credits")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class HackathonListResponse(BaseModel):
    total: int = Field(..., description="Total matching items count")
    page: int = Field(..., description="Current page number (1-indexed)")
    limit: int = Field(..., description="Page size limit")
    total_pages: int = Field(..., description="Total pages available")
    items: List[HackathonItem] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: str
    version: str = "1.0.0"
    database_connected: bool
    total_hackathons: int
    active_hackathons: int


class StatsResponse(BaseModel):
    total_hackathons: int
    sources: Dict[str, int]
    status_counts: Dict[str, int]
    formats: Optional[Dict[str, int]] = None
    total_benefits: Optional[int] = None
