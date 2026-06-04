from db.store import add_user


async def start_command(update, context):

    chat_id = update.effective_chat.id

    add_user(chat_id)

    await update.message.reply_text(
        "Subscribed successfully."
    )