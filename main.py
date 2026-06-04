from fetcher.devpost import fetch_hackathons
from fetcher.devfolio import DevfolioFetcher

from bot.notifier import send_message
from db.store import get_new_hackathons


def run_pipeline():

    all_hackathons = []

    sources = [
        ("Devpost", fetch_hackathons),
        ("Devfolio", DevfolioFetcher().fetch)
    ]

    for name, fetch_function in sources:

        try:

            print(f"\n[{name}] Fetching...")

            data = fetch_function()

            print(f"[{name}] {len(data)} fetched")

            all_hackathons.extend(data)

        except Exception as e:

            print(f"[{name}] ERROR: {e}")

    print(f"\n[TOTAL] {len(all_hackathons)} fetched")

    new_items = get_new_hackathons(all_hackathons)

    print(f"[NEW] {len(new_items)}")

    for hackathon in new_items:

        send_message(hackathon)


if __name__ == "__main__":
    run_pipeline()