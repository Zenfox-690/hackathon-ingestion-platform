from fetcher.devpost import fetch_hackathons
from bot.notifier import send_message
from db.store import get_new_hackathons


hackathons = fetch_hackathons()

new_items = get_new_hackathons(hackathons)

print(f"New hackathons: {len(new_items)}")

for hackathon in new_items:
    send_message(hackathon)