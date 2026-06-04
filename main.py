from fetcher.devpost import fetch_hackathons
from bot.notifier import send_message
from db.store import get_new_hackathons


def run_pipeline():
    print("[PIPELINE] Running...")

    hackathons = fetch_hackathons()

    new_items = get_new_hackathons(hackathons)

    print(f"[NEW] {len(new_items)} hackathons")

    for hackathon in new_items:
        send_message(hackathon)


if __name__ == "__main__":
    run_pipeline()