from pyrogram import Client, filters
from vgx.database.dfeed_db import add_to_queue, update_settings, get_chat_settings, queue

@Client.on_message(filters.command("add_drip") & filters.group)
async def add_content(c, m):
    # Ensure reply to media
    reply = m.reply_to_message
    if not reply or not (reply.photo or reply.video or reply.document):
        return await m.reply("❌ Please reply to a Photo, Video, or Document to add it to the drip.")
    
    file_id = None
    file_type = None
    if reply.photo:
        file_id = reply.photo.file_id
        file_type = "photo"
    elif reply.video:
        file_id = reply.video.file_id
        file_type = "video"
    else:
        file_id = reply.document.file_id
        file_type = "document"

    caption = reply.caption or ""
    await add_to_queue(m.chat.id, file_id, file_type, caption)
    
    count = await queue.count_documents({"chat_id": m.chat.id})
    await m.reply(f"📥 **Added to Drip!**\nItems in queue: `{count}`")

@Client.on_message(filters.command("start_drip") & filters.group)
async def start_drip_cmd(c, m):
    await update_settings(m.chat.id, {"is_active": True})
    await m.reply("🚀 **Drip Campaign Started!** The bot will post content based on your interval.")

@Client.on_message(filters.command("stop_drip") & filters.group)
async def stop_drip_cmd(c, m):
    await update_settings(m.chat.id, {"is_active": False})
    await m.reply("🛑 **Drip Campaign Paused.**")
