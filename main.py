from fetcher.devpost import fetch_hackathons
from bot.notifier import send_message


hackathons = fetch_hackathons()

first = hackathons[0]

send_message(first)