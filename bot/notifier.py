import asyncio
import os

from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from db.store import already_notified, generate_fingerprint, get_filters, get_users, mark_notified
from filters.relevance import calculate_score

load_dotenv()

_bot_instance = None


def get_bot():
    """Lazily initialize and cache the Telegram Bot instance."""
    global _bot_instance
    if _bot_instance is None:
        token = os.getenv("BOT_TOKEN")
        if token:
            _bot_instance = Bot(token)
    return _bot_instance


async def async_send_message(hackathon, bot_instance=None):
    """Asynchronously send notification for a hackathon to eligible users.

    Guarantees that mark_notified is ONLY called if delivery actually succeeds.
    """
    target_bot = bot_instance or get_bot()
    if not target_bot:
        print("[TELEGRAM] Warning: No BOT_TOKEN found or bot not configured. Skipping notifications.")
        return False

    users = get_users()
    fingerprint = generate_fingerprint(hackathon)

    for chat_id in users:
        filters = get_filters(chat_id)

        if filters:
            score = calculate_score(hackathon, filters)
            if not score:
                continue
        else:
            score = 0

        if already_notified(chat_id, fingerprint):
            continue

        text = (
            f"🚀 *New Hackathon*\n\n"
            f"*{hackathon['name']}*\n"
            f"Relevance: {score}\n"
            f"Deadline: {hackathon.get('deadline') or 'Unknown'}\n"
            f"Source: {hackathon.get('source', '')}\n\n"
            f"{hackathon.get('link', '')}"
        )

        keyboard = []
        if hackathon.get("link"):
            keyboard.append([InlineKeyboardButton("Open", url=hackathon["link"])])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        delivered = False
        try:
            await target_bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=reply_markup)
            delivered = True
        except Exception:
            # Fallback to plain text in case of unescaped Markdown syntax errors in hackathon name
            try:
                plain_text = text.replace("*", "").replace("_", "")
                await target_bot.send_message(chat_id=chat_id, text=plain_text, reply_markup=reply_markup)
                delivered = True
            except Exception as fallback_e:
                print(f"[TELEGRAM] Error sending to {chat_id}: {fallback_e}")

        if delivered:
            mark_notified(chat_id, fingerprint)
            print(f"[TELEGRAM] Sent to {chat_id}")
        else:
            print(f"[TELEGRAM] Delivery failed for {chat_id}; not marked as notified.")

    return True


def send_message(hackathon, bot_instance=None):
    """Synchronous entry point that safely invokes async_send_message."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, async_send_message(hackathon, bot_instance=bot_instance)).result()
    else:
        return asyncio.run(async_send_message(hackathon, bot_instance=bot_instance))
