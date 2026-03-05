from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply


from vgx.database.channel_db import update_reaction, save_channel, get_user_channels, create_live_post, channels_col

@Client.on_chat_member_updated()
async def track_new_channels(client, update):
    # Check if the bot was the one added, and if it was added to a channel
    if update.new_chat_member and update.new_chat_member.user.is_self:
        if update.chat.type.name == "CHANNEL":
            # update.from_user is the Admin who added the bot
            owner_id = update.from_user.id
            chat_id = update.chat.id
            title = update.chat.title
            
            await save_channel(chat_id, title, owner_id)
            
            # Send a confirmation to the admin's DMs
            try:
                await client.send_message(
                    owner_id, 
                    f"✅ **Channel Linked!**\nI am now ready to manage `{title}`.\nType /channel to create a post!"
                )
            except:
                pass

 

# Temporary storage for posts being created
DRAFTS = {}

def build_draft_menu(draft_id: int):
    draft = DRAFTS.get(draft_id)
    if not draft: return None
    
    reac_btn = "🟢 Reactions Added" if draft["use_reactions"] else "➕ Add Reactions"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Add URL Button", callback_data=f"draft_btn_{draft_id}"),
         InlineKeyboardButton(reac_btn, callback_data=f"draft_reac_{draft_id}")],
        [InlineKeyboardButton("🚀 Publish to Channel", callback_data=f"draft_publish_{draft_id}")]
    ])

@Client.on_message(filters.command("start") & filters.private)
async def start_wizard(client, message):
    channels = await get_user_channels(message.from_user.id)
    if not channels:
        return await message.reply("⚠️ **Welcome!** Please add me to your channel as an Admin first, then type /start again.")
        
    buttons = [[InlineKeyboardButton(ch["title"], callback_data=f"newpost_{ch['chat_id']}")] for ch in channels]
    await message.reply("✍️ **Post Creator**\nSelect the channel you want to post to:", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^newpost_(?P<chat_id>-?\d+)$"))
async def init_draft(client, query):
    chat_id = int(query.matches[0].group("chat_id"))
    uid = query.from_user.id
    
    # Create a fresh draft
    DRAFTS[uid] = {
        "chat_id": chat_id,
        "media_type": None,
        "media_id": None,
        "text": "",
        "buttons": [], # Format: [{"text": "Google", "url": "https://google.com"}]
        "use_reactions": False
    }
    
    await query.message.edit_text(
        "📝 **Awaiting Content**\n\nSend me the Text, Photo, or Video for your post now!"
    )

# --- Catch Media/Text for Draft ---
@Client.on_message(filters.private & ~filters.command("channel"))
async def catch_draft_cosntent(client, message):
    uid = message.from_user.id
    if uid not in DRAFTS or DRAFTS[uid].get("text") != "":
        # If they aren't in the middle of a draft, or already set the content, ignore or handle button replies
        if message.reply_to_message and "Send the button name and link" in message.reply_to_message.text:
            try:
                # Parse: "Button Name - https://link.com"
                parts = message.text.split("-", 1)
                DRAFTS[uid]["buttons"].append({"text": parts[0].strip(), "url": parts[1].strip()})
                await message.reply("✅ Button Added!", reply_markup=build_draft_menu(uid))
            except:
                await message.reply("❌ Invalid format. Use: `My Button - https://link.com`")
        return

    # Save content to draft
    draft = DRAFTS[uid]
    if message.photo:
        draft["media_type"], draft["media_id"] = "photo", message.photo.file_id
        draft["text"] = message.caption.markdown if message.caption else ""
    elif message.video:
        draft["media_type"], draft["media_id"] = "video", message.video.file_id
        draft["text"] = message.caption.markdown if message.caption else ""
    elif message.text:
        draft["media_type"], draft["text"] = "text", message.text.markdown

    await message.reply("✅ **Content Saved!**\nWhat would you like to add?", reply_markup=build_draft_menu(uid))

# --- Draft Tools & Publishing ---
@Client.on_callback_query(filters.regex(r"^draft_(?P<action>[a-z_]+)_(?P<uid>\d+)$"))
async def draft_actions(client, query):
    action = query.matches[0].group("action")
    uid = int(query.matches[0].group("uid"))
    draft = DRAFTS.get(uid)
    
    if action == "reac":
        draft["use_reactions"] = not draft["use_reactions"]
        await query.message.edit_reply_markup(reply_markup=build_draft_menu(uid))
        
    elif action == "btn":
        await query.message.reply(
            "🔗 **Add Button**\nReply to this message with the format:\n`Button Name - https://link.com`",
            reply_markup=ForceReply(selective=True)
        )
        await query.answer()
        
    elif action == "publish":
        # Build the Inline Keyboard
        kb = []
        if draft["buttons"]:
            for b in draft["buttons"]:
                kb.append([InlineKeyboardButton(b["text"], url=b["url"])])
        
        # We will add reaction buttons AFTER sending, because we need the message_id for the database
        reply_markup = InlineKeyboardMarkup(kb) if kb else None
        
        # Send it!
        try:
            if draft["media_type"] == "photo":
                msg = await client.send_photo(draft["chat_id"], photo=draft["media_id"], caption=draft["text"], reply_markup=reply_markup)
            elif draft["media_type"] == "video":
                msg = await client.send_video(draft["chat_id"], video=draft["media_id"], caption=draft["text"], reply_markup=reply_markup)
            else:
                msg = await client.send_message(draft["chat_id"], text=draft["text"], reply_markup=reply_markup)
            
            # If reactions are enabled, create DB entry and update the keyboard
            if draft["use_reactions"]:
                ch_data = await channels_col.find_one({"chat_id": draft["chat_id"]})
                emojis = ch_data.get("default_reactions", ["👍", "❤️"])
                
                post_id = await create_live_post(draft["chat_id"], msg.id, emojis)
                
                # Append reaction buttons to existing URL buttons
                reac_row = [InlineKeyboardButton(f"{e} 0", callback_data=f"react_{post_id}_{e}") for e in emojis]
                kb.append(reac_row)
                await msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(kb))

            await query.message.edit_text("🚀 **Post Published Successfully!**")
            del DRAFTS[uid] # Clear draft
            
        except Exception as e:
            await query.message.reply(f"❌ Failed to publish: {e}")


@Client.on_callback_query(filters.regex(r"^react_(?P<post_id>[0-9a-fA-F]{24})_(?P<emoji>.+)$"))
async def handle_reaction(client, query):
    post_id = query.matches[0].group("post_id")
    emoji = query.matches[0].group("emoji")
    user_id = query.from_user.id
    
    # 1. Update Database (Adds user if they haven't clicked, removes if they have)
    updated_post = await update_reaction(post_id, emoji, user_id)
    
    if not updated_post:
        return await query.answer("Post expired or deleted.", show_alert=True)
    
    # 2. Rebuild the Reaction Keyboard Row
    # We grab the existing keyboard so we don't accidentally delete the URL buttons
    existing_kb = query.message.reply_markup.inline_keyboard
    new_kb = []
    
    # Keep URL buttons (which don't start with 'react_')
    for row in existing_kb:
        if not row[0].callback_data or not row[0].callback_data.startswith("react_"):
            new_kb.append(row)
            
    # Build the new Reaction Row based on database counts
    reac_row = []
    for emj, users in updated_post["reactions"].items():
        count = len(users)
        count_str = f" {count}" if count > 0 else " 0"
        reac_row.append(
            # Using the emoji and the count dynamically
            client.types.InlineKeyboardButton(f"{emj}{count_str}", callback_data=f"react_{post_id}_{emj}")
        )
    
    new_kb.append(reac_row)
    
    # 3. Edit the message silently with the new counts
    try:
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_kb))
        await query.answer("Reaction updated!")
    except Exception:
        # Fails silently if they rapidly click and the message isn't modified
        await query.answer()

