import os
import requests

from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
from db.store import (
    get_users,
    get_filters,
    already_notified,
    mark_notified,
    generate_fingerprint
)
from filters.relevance import (
    calculate_score
)


def send_message(hackathon):

    users = get_users()

    for chat_id in users:

        filters = get_filters(chat_id)

        if filters:
            score = calculate_score(
                hackathon,
                filters
            )

            if not score:
                continue
        else:
            score = 0

        fingerprint = generate_fingerprint(hackathon)

        if already_notified(
            chat_id,
            fingerprint
        ):
            continue

        text = (
            f"🚀 *New Hackathon*\n\n"
            f"*{hackathon['name']}*\n"
            f"Relevance: {score}\n"
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

        mark_notified(
            chat_id,
            fingerprint
        )

        print(f"[TELEGRAM] Sent to {chat_id}")

