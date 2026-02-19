from pyrogram import Client, filters
from pyrogram.types import Message
from vgx.database.bday_db import *
from utils import is_admin
from config import *

@Client.on_message(filters.command("setbirthday") & filters.group)
async def set_birthday(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: `/setbirthday DD-MM [Timezone]`\nExample: `/setbirthday 25-12 Asia/Kolkata`")
    
    date_str = message.command[1]
    tz = message.command[2] if len(message.command) > 2 else "UTC"
    
    try:
        datetime.strptime(date_str, "%d-%m")
        pytz.timezone(tz)
    except:
        return await message.reply("❌ Invalid date or timezone!")
    
    save_birthday(message.from_user.id, message.chat.id, date_str, tz)
    await message.reply(f"✅ Birthday set to **{date_str}** in **{tz}**!")

@Client.on_message(filters.command("mybirthday") & filters.group)
async def my_birthday(client: Client, message: Message):
    doc = get_birthday(message.from_user.id, message.chat.id)
    if doc:
        await message.reply(f"🎂 Your birthday is set to **{doc['birthday']}** (Timezone: {doc['timezone']})")
    else:
        await message.reply("You haven't set your birthday yet. Use /setbirthday")
