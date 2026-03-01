from pyrogram import filters
from pyrogram.types import Message

from vgx.module.quotes_keyboards import main_menu
from vgx.database.quets_db2 import settings_col
from vgx import app  # app created in bot.py

@app.on_message(filters.command("quotes") & (filters.private | filters.group))
async def quotes_panel(_, message: Message):
    """Open the inline UI panel for the chat (works in groups and private)."""
    chat_id = message.chat.id
    # ensure default doc exists
    await settings_col.update_one(
        {"chat_id": chat_id},
        {"$setOnInsert": {
            "chat_id": chat_id,
            "enabled": False,
            "interval": None,
            "auto_delete": 0,
            "delete_last": False,
            "pin": False,
            "target_chat": None,
            "last_msg_id": None
        }},
        upsert=True
    )
    await message.reply("🌸 Random Quotes Scheduler — Control Panel", reply_markup=main_menu(chat_id))

@app.on_message(filters.command("settarget") & (filters.group | filters.private))
async def set_target(_, message: Message):
    """Set target chat id where quotes will be posted.
    Usage: /settarget <chat_id>
    Note: chat_id must be numeric (use -100... for supergroups)"""
    if len(message.command) != 2:
        return await message.reply_text("Usage: /settarget <chat_id>\nExample: /settarget -1001234567890")

    try:
        target_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("Chat id must be an integer.")

    await settings_col.update_one({"chat_id": message.chat.id},
                                  {"$set": {"target_chat": target_id}},
                                  upsert=True)
    await message.reply_text(f"🎯 Target chat set to `{target_id}`", parse_mode="markdown")
