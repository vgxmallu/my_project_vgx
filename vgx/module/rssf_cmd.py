from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.command("stafjrt") & filters.private)
async def start_cmd(client, message):
    text = "👋 Welcome to RSS Bot!\n\nUse `/addfeed <chat_id> <url>` to add a feed, or use `/myfeeds` to manage existing ones."
    await message.reply_text(text)

@Client.on_message(filters.command("addfeed"))
async def add_feed_cmd(client, message):
    args = message.text.split(" ", 2)
    if len(args) < 3:
        return await message.reply_text("Usage: `/addfeed -10012345678 https://example.com/rss`")
    
    chat_id = int(args[1])
    feed_url = args[2]
    
    await client.db.add_source(chat_id, feed_url)
    feeds = await client.db.get_chat_feeds(chat_id)
    feed_id = str(feeds[-1]["_id"])
    
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚙️ Customize Autoposting", callback_data=f"manage_{feed_id}")
    ]])
    await message.reply_text(f"✅ Feed added successfully!", reply_markup=markup)



@Client.on_message(filters.private & ~filters.command(["addfeedx"]))
async def handle_user_input(client, message):
    user_id = message.from_user.id
    
    if message.text == "/cancel":
        if user_id in client.user_states:
            del client.user_states[user_id]
        return await message.reply_text("❌ Action cancelled.")

    if user_id in client.user_states:
        state = client.user_states[user_id]
        feed_id = state["feed_id"]
        
        if state["action"] == "template":
            await client.db.update_setting(feed_id, "template", message.text.markdown)
            await message.reply_text("✅ Message Format successfully updated!")
            
        elif state["action"] == "url":
            await client.db.update_setting(feed_id, "feed_url", message.text)
            await message.reply_text("✅ Feed URL successfully updated!")
        
        # Clear the state
        del client.user_states[user_id]
 
