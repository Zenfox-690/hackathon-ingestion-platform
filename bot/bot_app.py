import os

from dotenv import load_dotenv

from telegram.ext import (
    Application,
    CommandHandler
)

from bot.commands import (
    start_command,
    filter_command,
    upcoming_command
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(
    CommandHandler("start", start_command)
)

app.add_handler(
    CommandHandler("filter", filter_command)
)

app.add_handler(
    CommandHandler(
        "upcoming",
        upcoming_command
    )
)

print("Bot running...")

app.run_polling()