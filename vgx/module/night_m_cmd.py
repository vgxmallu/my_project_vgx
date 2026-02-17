from pyrogram import Client, filters
from vgx.database.night_db import get_settings, update_settings
import pytz

# Helper to check if user is admin
async def is_admin(c, m):
    member = await c.get_chat_member(m.chat.id, m.from_user.id)
    return member.status in ("administrator", "creator")

@Client.on_message(filters.command("nightmode") & filters.group)
async def toggle_nightmode(c, m):
    if not await is_admin(c, m): return
    status = m.command[1].lower() == "on" if len(m.command) > 1 else False
    await update_settings(m.chat.id, {"enabled": status})
    await m.reply(f"🌙 **Night Mode:** {'Enabled' if status else 'Disabled'}")

@Client.on_message(filters.command("settimezone") & filters.group)
async def set_tz(c, m):
    if not await is_admin(c, m): return
    if len(m.command) < 2: return await m.reply("Usage: `/settimezone Asia/Kolkata`")
    tz_input = m.command[1]
    if tz_input not in pytz.all_timezones:
        return await m.reply("❌ Invalid Timezone.")
    await update_settings(m.chat.id, {"timezone": tz_input})
    await m.reply(f"📍 Timezone set to `{tz_input}`")

@Client.on_message(filters.command("setnight") & filters.group)
async def set_night_msg(c, m):
    if not await is_admin(c, m): return
    if not m.reply_to_message: return await m.reply("Reply to a message/photo to set it as Night alert.")
    
    data = {"night_msg": m.reply_to_message.caption or m.reply_to_message.text}
    if m.reply_to_message.photo:
        data["night_photo"] = m.reply_to_message.photo.file_id
    
    await update_settings(m.chat.id, data)
    await m.reply("✅ Night message updated.")

@Client.on_message(filters.command("settimes") & filters.group)
async def set_times(c, m):
    if not await is_admin(c, m): return
    # Usage: /settimes 22:00 07:00
    if len(m.command) < 3: return await m.reply("Usage: `/settimes 22:00 07:00`")
    await update_settings(m.chat.id, {"night_start": m.command[1], "night_end": m.command[2]})
    await m.reply(f"🕒 Night schedule: {m.command[1]} to {m.command[2]}")
