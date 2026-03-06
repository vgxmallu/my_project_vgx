from pyrogram import Client, filters
from vgx.database.imdb_db import add_to_queue
from datetime import datetime, timedelta

@Client.on_message(filters.command("addmovie") & filters.private)
async def add_movie_cmd(client, message):
    if len(message.command) < 3:
        return await message.reply("❌ **Usage:** `/addmovie <chat_id> <Movie Name>`\nExample: `/addmovie -100123 Inception`")
        
    chat_id = int(message.command[1])
    query = " ".join(message.command[2:])
    
    # Schedule it to be picked up immediately by the background loop
    await add_to_queue(chat_id, query, datetime.utcnow())
    await message.reply(f"✅ **Added to queue!**\nTarget: `{chat_id}`\nQuery: `{query}`")
