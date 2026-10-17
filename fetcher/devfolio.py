import html
import json
import os
import re
from urllib.parse import urlparse

import requests
from playwright.sync_api import sync_playwright

from config import FETCH_LIMIT, HEADLESS
from fetcher.base import BaseFetcher
from fetcher.utils import validate_hackathon
from filters.benefits import extract_special_benefits
from utils.dates import normalize_date
from utils.format import normalize_participation_format
from utils.urls import canonicalize_url

NAV_SLUGS = {"applied", "open", "upcoming", "past", "discover", "home", "blog"}
NAV_TITLES = {
    "your hackathons",
    "all upcoming hackathons",
    "all past hackathons",
    "all open hackathons",
    "open hackathons",
    "discover",
    "home",
    "blog",
}


def parse_devfolio_cards_from_html(html_content: str, limit: int = FETCH_LIMIT):
    """
    Parse valid Devfolio hackathons.
    Primary strategy: Extracts rich structured data from Next.js __NEXT_DATA__ hydration payload.
    Secondary fallback: Parses DOM cards, strictly excluding section navigation links.
    """
    hackathons = []
    seen_links = set()

    # Strategy 1: Extract from __NEXT_DATA__
    next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_content, re.DOTALL)
    if next_data_match:
        try:
            payload = json.loads(next_data_match.group(1))
            queries = payload.get("props", {}).get("pageProps", {}).get("dehydratedState", {}).get("queries", [])

            for q in queries:
                qdata = q.get("state", {}).get("data", {})
                if not isinstance(qdata, dict):
                    continue

                # Combine hackathon categories
                categories = [
                    ("open", qdata.get("open_hackathons", [])),
                    ("upcoming", qdata.get("upcoming_hackathons", [])),
                    ("past", qdata.get("past_hackathons", [])),
                    ("featured", qdata.get("featured_hackathons", [])),
                ]

                for cat_hint, items in categories:
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        if not isinstance(item, dict):
                            continue

                        name = (item.get("name") or "").strip()
                        slug = (item.get("slug") or "").strip()
                        if not name or not slug:
                            continue

                        raw_link = f"https://{slug}.devfolio.co"
                        canon_link = canonicalize_url(raw_link)
                        if not canon_link or canon_link in seen_links:
                            continue
                        seen_links.add(canon_link)

                        settings = item.get("settings") or {}
                        reg_ends_at = item.get("reg_ends_at") or settings.get("reg_ends_at")
                        reg_starts_at = item.get("reg_starts_at") or settings.get("reg_starts_at")
                        starts_at = item.get("starts_at")
                        ends_at = item.get("ends_at")

                        primary_deadline = reg_ends_at or ends_at
                        normalized_deadline = normalize_date(primary_deadline) or primary_deadline or "Unknown"

                        # Extract tags from themes
                        themes = item.get("themes") or []
                        tags = []
                        for t in themes:
                            if isinstance(t, dict):
                                tname = t.get("theme", {}).get("name") or t.get("name")
                            else:
                                tname = str(t)
                            if tname and tname.strip():
                                tags.append(tname.strip().lower())

                        # Determine online / in-person / hybrid / unknown format
                        is_online = item.get("is_online")
                        if is_online is None and isinstance(item.get("hackathon_setting"), dict):
                            is_online = item["hackathon_setting"].get("is_online")
                        raw_loc = None
                        if is_online is True:
                            raw_loc = "Online"
                        elif is_online is False:
                            raw_loc = "In-Person"
                        location = normalize_participation_format(raw_loc)

                        # Organizer / Description
                        participants = item.get("participants_count") or 0
                        desc = f"Devfolio Hackathon ({location}) • {participants} participants"

                        hackathon = {
                            "name": name,
                            "slug": slug,
                            "description": desc,
                            "tags": sorted(list(set(tags))),
                            "deadline": normalized_deadline,
                            "reg_starts_at": normalize_date(reg_starts_at) or reg_starts_at or "",
                            "reg_ends_at": normalize_date(reg_ends_at) or reg_ends_at or "",
                            "starts_at": normalize_date(starts_at) or starts_at or "",
                            "ends_at": normalize_date(ends_at) or ends_at or "",
                            "source_status": "ended" if cat_hint == "past" else cat_hint,
                            "prize": "Unknown",
                            "location": location,
                            "link": canon_link,
                            "source": "Devfolio",
                        }
                        hackathon["benefits"] = extract_special_benefits(hackathon)

                        if validate_hackathon(hackathon):
                            hackathons.append(hackathon)

                        if len(hackathons) >= limit:
                            break
                    if len(hackathons) >= limit:
                        break

            if hackathons:
                return hackathons
        except Exception as e:
            print(f"[DEVFOLIO] Warning: Failed to parse __NEXT_DATA__: {e}")

    # Strategy 2: DOM fallback for synthetic test HTML or pre-rendered cards
    pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(?:(?!</a>).)*?<h3[^>]*>(.*?)</h3>', re.DOTALL)
    matches = pattern.findall(html_content)

    for raw_link, raw_title in matches:
        raw_link = raw_link.strip()
        if raw_link.startswith("/"):
            raw_link = f"https://devfolio.co{raw_link}"

        canon_link = canonicalize_url(raw_link)
        if not canon_link:
            continue

        parsed = urlparse(canon_link)
        # Exclude devfolio.co main section navigation links
        if parsed.netloc in ("devfolio.co", "www.devfolio.co") and any(
            slug in parsed.path.lower() for slug in NAV_SLUGS
        ):
            continue

        clean_title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
        if not clean_title or clean_title.lower() in NAV_TITLES:
            continue

        if canon_link in seen_links:
            continue
        seen_links.add(canon_link)

        hackathon = {
            "name": clean_title,
            "description": "",
            "tags": [],
            "deadline": "Unknown",
            "prize": "Unknown",
            "link": canon_link,
            "source": "Devfolio",
        }

        if validate_hackathon(hackathon):
            hackathons.append(hackathon)

        if len(hackathons) >= limit:
            break

    return hackathons


class DevfolioFetcher(BaseFetcher):
    name = "Devfolio"
    timeout_seconds = 20

    def fetch(self):
        # Step 1: Try direct HTTP request (fast, reliable, gets full __NEXT_DATA__)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            )
        }
        try:
            res = requests.get("https://devfolio.co/hackathons", headers=headers, timeout=self.timeout_seconds)
            if res.status_code == 200 and "__NEXT_DATA__" in res.text:
                if os.path.exists("cache"):
                    with open("cache/devfolio.html", "w", encoding="utf-8") as f:
                        f.write(res.text)
                items = parse_devfolio_cards_from_html(res.text, limit=FETCH_LIMIT)
                if items:
                    return items
        except Exception as e:
            print(f"[DEVFOLIO] Direct fetch notice: {e}, falling back to Playwright.")

        # Step 2: Fallback to Playwright headless browser
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            try:
                context = browser.new_context(user_agent=headers["User-Agent"])
                page = context.new_page()
                page.goto("https://devfolio.co/hackathons", timeout=30000)

                try:
                    page.wait_for_selector("div[class*='HackathonCard'], script#__NEXT_DATA__", timeout=10000)
                except Exception:
                    page.wait_for_timeout(4000)

                content = page.content()
                if os.path.exists("cache"):
                    with open("cache/devfolio.html", "w", encoding="utf-8") as f:
                        f.write(content)

                return parse_devfolio_cards_from_html(content, limit=FETCH_LIMIT)
            finally:
                browser.close()
