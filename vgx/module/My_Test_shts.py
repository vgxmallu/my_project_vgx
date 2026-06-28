from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputRichMessage



@app.on_message(filters.private & filters.command("tt"))
async def stahgrt(client, message):
    # 1. Send the initial text message using valid Telegram HTML (<b> instead of <h1>)
    # We assign it to 'bot_msg' so we can capture its unique message ID
    bot_msg = await message.reply_text(
        "<b>Hey I am an Advanced Scheduler Bot</b>"
    )
    
    try:
        # 2. Replace the bot's message with the new checklist
        await client.edit_message_checklist(
            chat_id=message.chat.id,
            message_id=bot_msg.id,  # CRITICAL FIX: Edits the bot's message, not the user's
            checklist=types.InputChecklist(
               title="Hey I am Advanced Scheduler Bot",
               tasks=[
                   types.InputChecklistTask(id=1, text="Task 1"),
                   types.InputChecklistTask(id=2, text="Task 2")
               ]
           )
        )
    except AttributeError:
        # Safety fallback error if your specific Pyrogram fork layer 
        # doesn't fully support the edit_message_checklist wrapper yet
        await message.reply_text("❌ Checklist method not supported by this library layer.")

