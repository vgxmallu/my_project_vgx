from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.db import db

@Client.on_message(filters.command("startrss") & filters.private)
async def start_chsmd(client, message):
    text = "👋 Welcome to the RSS Autoposting Bot!\n\nTo add a feed to your group or channel, add me as an admin there, then use:\n`/addfeed <chat_id> <rss_url>`"
    await message.reply_text(text)

@Client.on_message(filters.command("addfeed"))
async def add_feed_cmd(client, message):
    args = message.text.split(" ", 2)
    if len(args) < 3:
        return await message.reply_text("Usage: `/addfeed -10012345678 https://example.com/rss`")
    
    chat_id = int(args[1])
    feed_url = args[2]

    await db.add_feed(chat_id, feed_url)
    
    # Simple inline button to manage this feed
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚙️ Manage this Feed", callback_data=f"manage_{chat_id}")
    ]])
    
    await message.reply_text(f"✅ Feed `{feed_url}` added to `{chat_id}` successfully!", reply_markup=markup)
