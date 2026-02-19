from pyrogram import Client, filters
from pyrogram.types import Message
from vgx.database.bday_db import *

@Client.on_message(filters.command("addevent") & filters.group)
async def add_event(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    # Simple parsing: /addevent Name 01-01 Message here
    args = " ".join(message.command[1:]).split(maxsplit=2)
    if len(args) < 3:
        return await message.reply("Usage: `/addevent EventName MM-DD Your message`")
    name, date, msg = args
    save_event(message.chat.id, name, date, msg)
    await message.reply(f"✅ Event **{name}** added for **{date}**!")

@Client.on_message(filters.new_chat_members & filters.group)
async def new_member(client: Client, message: Message):
    for member in message.new_chat_members:
        if member.id == (await client.get_me()).id:
            continue
        join_mmdd = datetime.now().strftime("%m-%d")
        save_member_anniversary(member.id, message.chat.id, join_mmdd)
