import os
import requests

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


def send_message(hackathon):
    text = (
        f"🚀 *New Hackathon*\n\n"
        f"*{hackathon['name']}*\n"
        f"Deadline: {hackathon['deadline']}\n"
        f"Source: {hackathon['source']}\n\n"
        f"{hackathon['link']}"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        },
        timeout=15
    )

    response.raise_for_status()

    print("[TELEGRAM] Sent")