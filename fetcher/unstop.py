import html
import json
import os
import re

from playwright.sync_api import sync_playwright

from config import FETCH_LIMIT, HEADLESS
from fetcher.base import BaseFetcher
from fetcher.utils import validate_hackathon
from filters.benefits import extract_special_benefits
from utils.dates import normalize_date
from utils.format import normalize_participation_format
from utils.urls import canonicalize_url

UNSTOP_NAV_SLUGS = {
    "online",
    "all",
    "upcoming",
    "past",
    "applied",
    "open",
    "closed",
    "college-students",
    "school-students",
    "engineering-students",
    "business-students",
    "internships",
    "jobs",
    "competitions",
    "explore",
    "categories",
    "trending",
    "featured",
    "home",
}

BADGE_WORDS = {"featured", "hot", "trending", "applied", "free", "live", "registered", "online", "offline"}


def parse_unstop_cards_from_html(html_content, limit=FETCH_LIMIT):
    """
    Parse Unstop hackathons with clean titles, credible event ID validation,
    explicit registration deadlines, and organization metadata.
    Rejects category and navigation links.
    """
    hackathons = []
    seen_links = set()

    # Strategy 1: Check for structured JSON-LD or hydration data if present
    json_ld_matches = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html_content, re.DOTALL
    )
    for jld in json_ld_matches:
        try:
            data = json.loads(jld)
            items = data if isinstance(data, list) else [data]
            for it in items:
                if it.get("@type") in ("Event", "Hackathon", "EducationEvent"):
                    url = it.get("url") or ""
                    canon = canonicalize_url(url)
                    if canon and re.search(r"-\d+$", canon) and canon not in seen_links:
                        seen_links.add(canon)
                        name = (it.get("name") or "").strip().splitlines()[0].strip()
                        raw_dl = it.get("endDate") or it.get("registrationEndDate")
                        norm_dl = normalize_date(raw_dl) if raw_dl else "Unknown"
                        loc = normalize_participation_format(it.get("eventAttendanceMode"))
                        h_dict = {
                            "name": name,
                            "description": it.get("description") or "",
                            "tags": [],
                            "deadline": norm_dl,
                            "prize": "Unknown",
                            "location": loc,
                            "link": canon,
                            "source": "Unstop",
                            "created_at": it.get("startDate") or "",
                        }
                        h_dict["benefits"] = extract_special_benefits(h_dict)
                        if validate_hackathon(h_dict):
                            hackathons.append(h_dict)
                            if len(hackathons) >= limit:
                                return hackathons
        except Exception:
            pass

    # Strategy 2: Card parsing with strict title and slug filtering
    link_pattern = re.compile(r'<a[^>]+href=["\'](/hackathons/[^"\']+)["\'][^>]*>(.*?)</a>', re.DOTALL)
    matches = link_pattern.findall(html_content)

    for href, content in matches:
        slug = href.strip("/").split("/")[-1].lower()

        # Reject navigation and category links
        if slug in UNSTOP_NAV_SLUGS or len(slug.split("-")) < 2:
            continue

        raw_link = f"https://unstop.com{href}" if href.startswith("/") else href

        canon_link = canonicalize_url(raw_link)
        if not canon_link or canon_link in seen_links:
            continue

        # Extract heading tags or text inside card
        heading_match = re.search(r"<h[1-6][^>]*>(.*?)</h[1-6]>", content, re.DOTALL)
        if heading_match:
            raw_title_block = heading_match.group(1)
        else:
            text_only = re.sub(r"<[^>]+>", "\n", content)
            raw_title_block = text_only

        # Clean title: strip HTML, take first meaningful non-badge line
        clean_text = html.unescape(re.sub(r"<[^>]+>", "\n", raw_title_block)).strip()
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

        clean_title = ""
        for line in lines:
            line_lower = line.lower()
            if line_lower in BADGE_WORDS:
                continue
            # Strip dynamic countdown timers
            line_clean = re.sub(
                r"\s*\b\d+\s*(?:days?|hours?|mins?|minutes?|secs?|seconds?)\s*left\b.*",
                "",
                line,
                flags=re.IGNORECASE,
            ).strip()
            # Strip 'Posted <Date>'
            line_clean = re.sub(r"\s*\bPosted\s+[A-Za-z]+\s+\d+.*", "", line_clean, flags=re.IGNORECASE).strip()
            if line_clean and line_clean.lower() not in ("unknown", ""):
                clean_title = line_clean
                break

        if not clean_title or clean_title.lower() == "unknown":
            continue

        seen_links.add(canon_link)

        # Extract verified registration deadline ONLY from explicit registration cues
        # Do not confuse event end date or posted date with registration deadline
        deadline_match = re.search(
            r"\b(?:Registration\s+Deadline|Deadline|Registration\s+closes|Closes\s+on)\s*:?\s*([A-Za-z]+\s+\d+,\s+\d{4})",
            content,
            re.IGNORECASE,
        )
        deadline = normalize_date(deadline_match.group(1)) if deadline_match else "Unknown"

        # Check for posted date separately
        posted_match = re.search(r"\bPosted\s+([A-Za-z]+\s+\d+,\s+\d{4})", content, re.IGNORECASE)
        created_at_hint = normalize_date(posted_match.group(1)) if posted_match else ""

        # Extract format (Online, In-Person, Hybrid, Unknown)
        location = normalize_participation_format(None, text_hints=content)

        # Extract organizer/university if available
        desc = ""
        org_match = re.search(
            r'<div[^>]*class=["\'][^"\']*(?:sub-title|college-name|org-name)[^"\']*["\'][^>]*>(.*?)</div>',
            content,
            re.DOTALL,
        )
        if org_match:
            desc = html.unescape(re.sub(r"<[^>]+>", "", org_match.group(1))).strip()

        hackathon = {
            "name": clean_title,
            "description": desc,
            "tags": [],
            "deadline": deadline or "Unknown",
            "prize": "Unknown",
            "location": location,
            "link": canon_link,
            "source": "Unstop",
            "created_at": created_at_hint or "",
        }
        hackathon["benefits"] = extract_special_benefits(hackathon)

        if validate_hackathon(hackathon):
            hackathons.append(hackathon)

        if len(hackathons) >= limit:
            break

    return hackathons


class UnstopFetcher(BaseFetcher):
    name = "Unstop"

    def fetch(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            try:
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/137.0.0.0 Safari/537.36"
                    )
                )

                page = context.new_page()
                page.goto("https://unstop.com/hackathons", timeout=30000)

                try:
                    page.wait_for_selector("a[href*='/hackathons/']", timeout=10000)
                except Exception:
                    page.wait_for_timeout(4000)

                content = page.content()
                hackathons = parse_unstop_cards_from_html(content, limit=FETCH_LIMIT)

                if os.path.exists("cache") and hackathons:
                    with open("cache/unstop.html", "w", encoding="utf-8") as f:
                        f.write(content)

                return hackathons
            finally:
                browser.close()
