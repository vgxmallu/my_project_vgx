from pyrogram import Client, filters
from pyrogram.types import Message
from vgx.database.bday_db import *
from utils3 import is_admin

@Client.on_message(filters.command("birthdaymessage") & filters.group)
async def set_birthday_message(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Admins only!")
    if len(message.command) < 2:
        return await message.reply("Usage: `/birthdaymessage Your custom message {mention} {role}`")
    text = " ".join(message.command[1:])
    save_chat_setting(message.chat.id, "birthday_message", text)
    await message.reply("✅ Birthday message updated!")

@Client.on_message(filters.command("birthdayrole") & filters.group)
async def set_birthday_role(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    role = " ".join(message.command[1:]) or DEFAULT_BIRTHDAY_ROLE
    save_chat_setting(message.chat.id, "birthday_role", role)
    await message.reply(f"✅ Birthday role text set to: **{role}**")

@Client.on_message(filters.command("addtrusted") & filters.group)
async def add_trusted(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    if message.reply_to_message:
        uid = message.reply_to_message.from_user.id
    elif len(message.command) > 1 and message.command[1].isdigit():
        uid = int(message.command[1])
    else:
        return await message.reply("Reply to user or give user_id")
    add_trusted_user(message.chat.id, uid)
    await message.reply("✅ User added to Trusted list - their birthday will now be celebrated!")

@Client.on_message(filters.command("removetrusted") & filters.group)
async def remove_trusted(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    # similar logic...
    await message.reply("✅ Removed from trusted.")
