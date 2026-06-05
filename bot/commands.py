from db.store import (
    add_user,
    add_filter,
    remove_filter,
    clear_filters,
    get_filters,
    get_upcoming,
    get_stats
)
from logs.logger import log

async def start_command(update, context):

    chat_id = update.effective_chat.id

    log(f"/start used by {chat_id}")

    add_user(chat_id)

    await update.message.reply_text(
        "Subscribed successfully."
    )


async def filter_command(update, context):

    chat_id = update.effective_chat.id

    log(f"/filter used by {chat_id}")

    if not context.args:

        await update.message.reply_text(
            "Usage: /filter ai"
        )

        return

    keyword = context.args[0].lower()

    add_filter(chat_id, keyword)

    await update.message.reply_text(
        f"Filter added: {keyword}"
    )


async def unfilter_command(update, context):

    chat_id = update.effective_chat.id

    log(f"/unfilter used by {chat_id}")

    if not context.args:

        await update.message.reply_text(
            "Usage: /unfilter ai"
        )

        return

    keyword = context.args[0].lower()

    remove_filter(chat_id, keyword)

    await update.message.reply_text(
        f"Removed filter: {keyword}"
    )


async def clearfilters_command(update, context):

    chat_id = update.effective_chat.id

    log(f"/clearfilters used by {chat_id}")

    clear_filters(chat_id)

    await update.message.reply_text(
        "All filters cleared."
    )


async def filters_command(update, context):

    chat_id = update.effective_chat.id

    log(f"/filters used by {chat_id}")

    filters = get_filters(chat_id)

    if not filters:

        await update.message.reply_text(
            "No filters set."
        )

        return

    text = "Your filters:\n\n"

    for keyword in filters:

        text += f"- {keyword}\n"

    await update.message.reply_text(text)


async def upcoming_command(update, context):

    chat_id = update.effective_chat.id

    log(f"/upcoming used by {chat_id}")

    hackathons = get_upcoming()

    if not hackathons:

        await update.message.reply_text(
            "No hackathons found."
        )

        return

    text = "🚀 Upcoming Hackathons\n\n"

    for name, deadline, source in hackathons:

        text += (
            f"{name}\n"
            f"Deadline: {deadline}\n"
            f"Source: {source}\n\n"
        )

    await update.message.reply_text(text)


async def help_command(update, context):

    chat_id = update.effective_chat.id

    log(f"/help used by {chat_id}")

    text = (
        "🚀 Commands\n\n"
        "/start - Register\n"
        "/stats - System statistics\n"
        "/filter ai - Add filter\n"
        "/unfilter ai - Remove filter\n"
        "/filters - View filters\n"
        "/clearfilters - Remove all filters\n"
        "/upcoming - View hackathons\n"
    )

    await update.message.reply_text(text)


async def stats_command(update, context):

    stats = get_stats()

    text = (
        "📊 System Stats\n\n"
        f"Hackathons: {stats['hackathons']}\n"
        f"Users: {stats['users']}\n"
        f"Filters: {stats['filters']}"
    )

    await update.message.reply_text(text)