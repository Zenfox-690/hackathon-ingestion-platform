from playwright.sync_api import sync_playwright

from config import FETCH_LIMIT, HEADLESS
from fetcher.base import BaseFetcher
from utils.dates import normalize_date


class UnstopFetcher(BaseFetcher):

    def fetch(self):

        with sync_playwright() as p:

            browser = p.chromium.launch(headless=HEADLESS)

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/137.0.0.0 Safari/537.36"
                )
            )

            page = context.new_page()

            page.goto("https://unstop.com/hackathons")

            page.wait_for_timeout(5000)

            cards = page.locator("a[href*='/hackathons/']")

            hackathons = []
            seen_links = set()

            count = min(cards.count(), FETCH_LIMIT)

            for i in range(count):

                card = cards.nth(i)

                title = card.inner_text().strip()

                link = card.get_attribute("href")

                if link and link.startswith("/"):

                    link = f"https://unstop.com{link}"

                if not link or link in seen_links:
                    continue

                seen_links.add(link)

                hackathon = {
                    "name": title,
                    "description": "",
                    "tags": [],
                    "deadline": normalize_date("Unknown") or "Unknown",
                    "prize": "Unknown",
                    "link": link,
                    "source": "Unstop"
                }

                hackathons.append(hackathon)

            with open("cache/unstop.html", "w", encoding="utf-8") as f:
                f.write(page.content())

            browser.close()

            return hackathons