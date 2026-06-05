import os

from dotenv import load_dotenv

from telegram.ext import (
    Application,
    CommandHandler
)

from bot.commands import (
    start_command,
    filter_command,
    filters_command,
    upcoming_command,
    unfilter_command,
    clearfilters_command,
    help_command,
    stats_command
)
from startup_checks import validate_environment

load_dotenv()

validate_environment()

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
        "filters",
        filters_command
    )
)

app.add_handler(
    CommandHandler(
        "upcoming",
        upcoming_command
    )
)

app.add_handler(
    CommandHandler(
        "unfilter",
        unfilter_command
    )
)

app.add_handler(
    CommandHandler(
        "clearfilters",
        clearfilters_command
    )
)

app.add_handler(
    CommandHandler(
        "help",
        help_command
    )
)

app.add_handler(
    CommandHandler(
        "stats",
        stats_command
    )
)

print("Bot running...")

app.run_polling()