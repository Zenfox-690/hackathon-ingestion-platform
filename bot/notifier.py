import os
import requests

from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
from db.store import (
    get_users,
    get_filters
)


def send_message(hackathon):

    users = get_users()

    for chat_id in users:

        filters = get_filters(chat_id)

        if filters and not matches_filters(
            hackathon,
            filters
        ):
            continue

        text = (
            f"🚀 *New Hackathon*\n\n"
            f"*{hackathon['name']}*\n"
            f"Deadline: {hackathon['deadline']}\n"
            f"Source: {hackathon['source']}\n\n"
            f"{hackathon['link']}"
        )

        url = (
            f"https://api.telegram.org/"
            f"bot{BOT_TOKEN}/sendMessage"
        )

        response = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            },
            timeout=15
        )

        response.raise_for_status()

        print(f"[TELEGRAM] Sent to {chat_id}")

def matches_filters(hackathon, filters):

    title = hackathon["name"].lower()

    return any(
        keyword in title
        for keyword in filters
    )