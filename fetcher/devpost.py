from typing import Any, Dict, List

import requests

from fetcher.base import BaseFetcher
from utils.dates import normalize_date, parse_date_range
from utils.urls import canonicalize_url


def parse_devpost_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse raw Devpost API item dictionaries into normalized hackathon records."""
    hackathons = []
    seen_links = set()

    for item in items:
        raw_link = item.get("url")
        link = canonicalize_url(raw_link)

        if not link or link in seen_links:
            continue

        seen_links.add(link)

        # Extract tags from themes if present
        raw_themes = item.get("themes") or []
        tags = []
        if isinstance(raw_themes, list):
            for t in raw_themes:
                if isinstance(t, dict) and "name" in t:
                    tags.append(t["name"].lower().strip())
                elif isinstance(t, str):
                    tags.append(t.lower().strip())

        # Clean prize amount
        prize = item.get("prize_amount") or "Unknown"
        if isinstance(prize, (int, float)):
            prize = f"${prize:,.0f}"

        # Extract location/host
        location = (
            item.get("displayed_location", {}).get("location")
            if isinstance(item.get("displayed_location"), dict)
            else "Online"
        )
        if not location:
            location = "Online"

        # Date and submission period parsing
        sub_period = item.get("submission_period_dates") or ""
        reg_start, reg_end = parse_date_range(sub_period)
        deadline = reg_end or normalize_date(sub_period) or sub_period or "Unknown"

        open_state = item.get("open_state") or ""

        hackathons.append(
            {
                "name": (item.get("title") or "").strip(),
                "description": (item.get("organization_name") or "").strip(),
                "tags": sorted(list(set(tags))),
                "deadline": deadline,
                "reg_starts_at": reg_start or "",
                "reg_ends_at": reg_end or "",
                "source_status": open_state,
                "prize": str(prize),
                "location": location,
                "link": link,
                "source": "Devpost",
            }
        )

    return hackathons


def fetch_hackathons(timeout: int = 15) -> List[Dict[str, Any]]:
    url = "https://devpost.com/api/hackathons"

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return parse_devpost_items(data.get("hackathons", []))
    except requests.RequestException as e:
        print(f"[ERROR] Devpost fetch failed: {e}")
        return []


class DevpostFetcher(BaseFetcher):
    name = "Devpost"
    timeout_seconds = 15

    def fetch(self) -> List[Dict[str, Any]]:
        return fetch_hackathons(timeout=self.timeout_seconds)
