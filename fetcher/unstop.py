import html
import os
import re

from playwright.sync_api import sync_playwright

from config import FETCH_LIMIT, HEADLESS
from fetcher.base import BaseFetcher
from fetcher.utils import validate_hackathon
from utils.dates import normalize_date
from utils.urls import canonicalize_url


def parse_unstop_cards_from_html(html_content, limit=FETCH_LIMIT):
    """
    Parse Unstop hackathons with clean titles, accurate deadline separation
    (avoiding treating 'Posted date' as deadline), and organization metadata.
    """
    link_pattern = re.compile(r'<a[^>]+href=["\'](/hackathons/[^"\']+)["\'][^>]*>(.*?)</a>', re.DOTALL)
    matches = link_pattern.findall(html_content)
    hackathons = []
    seen_links = set()

    for href, content in matches:
        # Check for heading tags inside card
        heading_match = re.search(r"<h[1-6][^>]*>(.*?)</h[1-6]>", content, re.DOTALL)
        if heading_match:
            raw_title = heading_match.group(1)
        else:
            text_only = re.sub(r"<[^>]+>", "\n", content)
            lines = [line.strip() for line in text_only.splitlines() if line.strip()]
            raw_title = lines[0] if lines else "Unknown"

        clean_title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()

        # Strip dynamic countdown timers (e.g. '26 days left', '13 hours left', '1 day left')
        clean_title = re.sub(
            r"\s*\b\d+\s*(?:days?|hours?|mins?|minutes?|secs?|seconds?)\s*left\b.*",
            "",
            clean_title,
            flags=re.IGNORECASE,
        ).strip()

        # Strip 'Posted <Date>' or extraneous trailing metadata
        clean_title = re.sub(r"\s*\bPosted\s+[A-Za-z]+\s+\d+.*", "", clean_title, flags=re.IGNORECASE).strip()

        if not clean_title or clean_title.lower() == "unknown":
            continue

        raw_link = f"https://unstop.com{href}" if href.startswith("/") else href
        canon_link = canonicalize_url(raw_link)
        if not canon_link or canon_link in seen_links:
            continue
        seen_links.add(canon_link)

        # Extract verified deadline ONLY from Deadline / Ends on / Registration Closes
        # Crucial fix: Do NOT treat 'Posted Jun 4' as the deadline!
        deadline_match = re.search(
            r"\b(?:Deadline|Ends\s+on|Registration\s+closes|Closes\s+on)\s*:?\s*([A-Za-z]+\s+\d+,\s+\d{4})",
            content,
            re.IGNORECASE,
        )
        deadline = normalize_date(deadline_match.group(1)) if deadline_match else "Unknown"

        # Check for posted date separately as discovery hint
        posted_match = re.search(r"\bPosted\s+([A-Za-z]+\s+\d+,\s+\d{4})", content, re.IGNORECASE)
        created_at_hint = normalize_date(posted_match.group(1)) if posted_match else ""

        # Extract format (Online vs In-Person)
        location = "Online"
        if re.search(r"\bOffline|In-Person|On-Campus\b", content, re.IGNORECASE):
            location = "In-Person"

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
