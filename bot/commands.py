from db.store import (
    add_user,
    add_filter
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