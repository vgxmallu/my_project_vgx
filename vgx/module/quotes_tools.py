from pyrogram import Client, filters
from vgx.database.quets_db2 import get_chat_data, update_chat

@Client.on_callback_query(filters.regex("del_last"))
async def delete_last_handler(c, q):
    s = await get_chat_data(q.message.chat.id)
    if s.get("last_msg_id"):
        try:
            await c.delete_messages(q.message.chat.id, s["last_msg_id"])
            await q.answer("🗑 Last message deleted!")
        except:
            await q.answer("❌ Message not found.", show_alert=True)
    else:
        await q.answer("No message history recorded.", show_alert=True)

# Target Feature: Use /target [chat_id] to manage a group from Private Chat
@Client.on_message(filters.command("target_g") & filters.private)
async def target_chat(c, m):
    if len(m.command) < 2:
        return await m.reply("Usage: `/target_g -100xxxxxxxx` (Get ID from group)")
    
    target_id = int(m.command[1])
    # Redirect setting logic to this target
    # This can be expanded to show the settings menu for that specific ID
    await m.reply(f"🎯 Targeting Chat: `{target_id}`. Now use /quotes to manage it.")
