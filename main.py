from fetcher.devpost import fetch_hackathons
from fetcher.devfolio import DevfolioFetcher
from fetcher.unstop import UnstopFetcher

from bot.notifier import send_message
from db.store import get_new_hackathons


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

            print(f"\n[{name}] Fetching...")

            data = fetch_function()

            print(f"[{name}] {len(data)} fetched")

            source_counts[name] = len(data)

            all_hackathons.extend(data)

        except Exception as e:

            print(f"[{name}] ERROR: {e}")

    print(f"\n[TOTAL] {len(all_hackathons)} fetched")

    print("\n[SOURCE SUMMARY]")

    for source, count in source_counts.items():

        print(f"{source}: {count}")

    new_items = get_new_hackathons(all_hackathons)

    print(f"[NEW] {len(new_items)}")

    for hackathon in new_items:

        send_message(hackathon)


if __name__ == "__main__":
    run_pipeline()