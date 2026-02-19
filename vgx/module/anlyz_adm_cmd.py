from pyrogram import Client, filters
from vgx.module.anylz_schedul import schedule_golden_msg
from vgx.database.anlys_db import promos

@Client.on_message(filters.command("schedule_best") & filters.group)
async def cmd_sched(c, m):
    # Usage: /schedule_best This is my message
    if len(m.command) < 2:
        return await m.reply("Usage: `/schedule_best [message]`")
    
    text = m.text.split(None, 1)[1]
    time_str = await schedule_golden_msg(c, m.chat.id, text)
    
    await m.reply(f"📅 **Scheduled!**\nBased on your traffic, this will post at: `{time_str}` (Golden Hour)")

@Client.on_message(filters.command("set_viral_promo") & filters.group)
async def set_promo(c, m):
    # Saves a message to be used when viral spike is detected
    if not m.reply_to_message:
        return await m.reply("Reply to the message you want to auto-post during viral spikes.")
    
    # Save the ID/Text
    await promos.update_one(
        {"chat_id": m.chat.id}, 
        {"$set": {"text": m.reply_to_message.text or "Promo!"}}, 
        upsert=True
    )
    await m.reply("🔥 **Viral Promo Set!** If chat goes crazy, I'll post this.")
