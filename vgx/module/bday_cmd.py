from pyrogram import Client, filters
from vgx.database.bday_db import chats

@Client.on_message(filters.command("setbirthdaymessage") & filters.group)
async def set_msg(c, m):
    if len(m.command) < 2: return await m.reply("Usage: `/setbirthdaymessage 🎂 Happy Bday {mention}!`")
    new_msg = m.text.split(None, 1)[1]
    await chats.update_one({"chat_id": m.chat.id}, {"$set": {"bday_msg": new_msg}})
    await m.reply("✅ Birthday message template updated!")

@Client.on_message(filters.command("birthdayrole") & filters.group)
async def set_role(c, m):
    role_name = m.text.split(None, 1)[1]
    await chats.update_one({"chat_id": m.chat.id}, {"$set": {"bday_role": role_name}})
    await m.reply(f"✅ Birthday 'Role' title set to: **{role_name}**")

@Client.on_message(filters.command("addtrusted") & filters.group)
async def add_trusted(c, m):
    if not m.reply_to_message: return await m.reply("Reply to a user to trust them.")
    target_id = m.reply_to_message.from_user.id
    await chats.update_one({"chat_id": m.chat.id}, {"$addToSet": {"trusted_users": target_id}})
    await m.reply(f"✅ User added to Trusted List. Only they will get birthday celebrations!")

@Client.on_message(filters.command("addevent") & filters.group)
async def add_event(c, m):
    # Format: /addevent Name MM-DD Message
    args = m.command
    if len(args) < 4: return await m.reply("Usage: `/addevent NewYear 01-01 Happy New Year!`")
    event_data = {"name": args[1], "date": args[2], "msg": " ".join(args[3:])}
    await chats.update_one({"chat_id": m.chat.id}, {"$push": {"events": event_data}})
    await m.reply(f"✅ Event '{args[1]}' scheduled for {args[2]}!")
