from db.store import (
    add_user,
    add_filter,
    get_upcoming
)

async def start_command(update, context):

    chat_id = update.effective_chat.id

    add_user(chat_id)

    await update.message.reply_text(
        "Subscribed successfully."
    )


async def filter_command(update, context):

    chat_id = update.effective_chat.id

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


async def upcoming_command(update, context):

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