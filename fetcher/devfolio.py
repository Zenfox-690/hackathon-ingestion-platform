from playwright.sync_api import sync_playwright

from config import FETCH_LIMIT, HEADLESS
from fetcher.base import BaseFetcher
from fetcher.utils import validate_hackathon


class DevfolioFetcher(BaseFetcher):

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

            page.goto("https://devfolio.co/hackathons")

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

                    link = f"https://devfolio.co{link}"

                if not link or link in seen_links:
                    continue

                seen_links.add(link)

                hackathon = {
                    "name": title,
                    "description": "",
                    "tags": [],
                    "deadline": "Unknown",
                    "prize": "Unknown",
                    "link": link,
                    "source": "Devfolio"
                }

                if validate_hackathon(hackathon):
                    hackathons.append(hackathon)

            with open("cache/devfolio.html", "w", encoding="utf-8") as f:
                f.write(page.content())

            page.screenshot(path="debug.png")
            browser.close()

            return hackathons