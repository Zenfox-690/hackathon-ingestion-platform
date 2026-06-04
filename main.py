from fetcher.devpost import fetch_hackathons
from fetcher.devfolio import DevfolioFetcher
from fetcher.unstop import UnstopFetcher

from bot.notifier import send_message
from db.store import get_new_hackathons
from logs.logger import log


def run_pipeline():

    all_hackathons = []

    source_counts = {}

    sources = [
    ("Devpost", fetch_hackathons),
    ("Devfolio", DevfolioFetcher().fetch),
    ("Unstop", UnstopFetcher().fetch)
]

    for name, fetch_function in sources:

        try:

            log(f"\n[{name}] Fetching...")

            data = fetch_function()

            if not data:
                log(f"[WARNING] {name} returned no data")

            log(f"[{name}] {len(data)} fetched")

            source_counts[name] = len(data)

            all_hackathons.extend(data)

        except Exception as e:

            log(f"[{name}] ERROR: {e}")

    log(f"\n[TOTAL] {len(all_hackathons)} fetched")

    log("\n[SOURCE SUMMARY]")

    for source, count in source_counts.items():

        log(f"{source}: {count}")

    new_items = get_new_hackathons(all_hackathons)

    log(f"[NEW] {len(new_items)}")

    for hackathon in new_items:
        print(hackathon["name"])

    log(f"[SENDING] {len(new_items)} to notifier")

    for hackathon in new_items:

        send_message(hackathon)


if __name__ == "__main__":
    run_pipeline()