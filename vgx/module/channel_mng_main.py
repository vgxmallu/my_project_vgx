#vgx.database.channel_db

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from vgx.database.channel_db import get_user, get_user_channels, save_channel, get_channel, create_live_post, update_reaction

def build_dashboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Create Post", callback_data="dash_create"),
         InlineKeyboardButton("⚙️ Settings", callback_data="dash_settings")],
        [InlineKeyboardButton("📚 My Channels", callback_data="dash_channels"),
         InlineKeyboardButton("🌎 Timezone", callback_data="dash_tz")]
    ])

@Client.on_message(filters.command("setch") & filters.private)
async def starchct_cmd(client, message):
    user = await get_user(message.from_user.id)
    text = (
        "👋 **Welcome to Channel Manager!**\n\n"
        "I can help you create interactive posts, manage auto-approvals, and track live reactions.\n\n"
        f"🌍 **Your Timezone:** `{user['timezone']}`\n"
        "*(Add me to your channel as an Admin to get started!)*"
    )
    await message.reply(text, reply_markup=build_dashboard())

@Client.on_callback_query(filters.regex(r"^dash_main$"))
async def back_to_main(client, query):
    await query.message.edit_text("👇 **Main Menu**", reply_markup=build_dashboard())


#:+&++&+&((-(-(-(-(-(


@Client.on_chat_member_updated()
async def track_new_channels(client, update):
    if update.new_chat_member and update.new_chat_member.user.is_self:
        if update.chat.type.name == "CHANNEL":
            owner_id = update.from_user.id
            chat_id = update.chat.id
            title = update.chat.title
            
            await save_channel(chat_id, title, owner_id)
            try:
                await client.send_message(owner_id, f"✅ **Channel Linked!**\nI am now managing `{title}`.")
            except:
                pass


#™{^÷^^×^{^^{^{


DRAFTS = {}

def build_draft_menu(uid: int):
    draft = DRAFTS.get(uid)
    if not draft: return None
    
    # Check if custom reactions are set
    reac_btn = f"🟢 Reactions: {' '.join(draft['reactions'])}" if draft['reactions'] else "➕ Add Custom Reactions"
    sig_btn = "🟢 Signature: ON" if draft['use_sig'] else "🔴 Signature: OFF"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Add URL Button", callback_data=f"wiz_btn_{uid}")],
        [InlineKeyboardButton(reac_btn, callback_data=f"wiz_reac_{uid}")],
        [InlineKeyboardButton(sig_btn, callback_data=f"wiz_sig_{uid}")],
        [InlineKeyboardButton("🚀 Publish Now", callback_data=f"wiz_publish_{uid}"),
         InlineKeyboardButton("🗑 Cancel", callback_data=f"wiz_cancel_{uid}")]
    ])

@Client.on_callback_query(filters.regex(r"^dash_create$"))
async def init_draft(client, query):
    channels = await get_user_channels(query.from_user.id)
    if not channels:
        return await query.answer("⚠️ Add me to a channel first!", show_alert=True)
        
    buttons = [[InlineKeyboardButton(ch["title"], callback_data=f"wiz_start_{ch['chat_id']}")] for ch in channels]
    await query.message.edit_text("✍️ **Select Target Channel:**", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^wiz_start_(?P<chat_id>-?\d+)$"))
async def ask_content(client, query):
    chat_id = int(query.matches[0].group("chat_id"))
    uid = query.from_user.id
    
    DRAFTS[uid] = {
        "chat_id": chat_id, "media_type": None, "media_id": None,
        "text": "", "buttons": [], "reactions": [], "use_sig": False
    }
    await query.message.edit_text("📝 **Send me your content!**\n(Send Text, a Photo, or a Video)")

@Client.on_message(filters.private & ~filters.command("dratf"))
async def catch_draft_content(client, message):
    uid = message.from_user.id
    
    # Handle Forced Replies (Buttons and Custom Reactions)
    if message.reply_to_message:
        reply_text = message.reply_to_message.text
        if "🔗 Add URL Button" in reply_text:
            try:
                name, url = message.text.split("-", 1)
                DRAFTS[uid]["buttons"].append({"text": name.strip(), "url": url.strip()})
                await message.reply("✅ Button added!", reply_markup=build_draft_menu(uid))
            except:
                await message.reply("❌ Invalid format. Use: `Name - https://link.com`")
            return
        elif "👍 Custom Reactions" in reply_text:
            DRAFTS[uid]["reactions"] = message.text.strip().split()[:6]
            await message.reply("✅ Custom reactions saved!", reply_markup=build_draft_menu(uid))
            return

    # Handle Initial Content
    if uid not in DRAFTS or DRAFTS[uid]["text"] != "": return
    
    draft = DRAFTS[uid]
    if message.photo:
        draft["media_type"], draft["media_id"] = "photo", message.photo.file_id
    elif message.video:
        draft["media_type"], draft["media_id"] = "video", message.video.file_id
        
    draft["text"] = message.caption.html if message.caption else (message.text.html if message.text else "")
    await message.reply("✅ **Content Saved!** Customize your post below:", reply_markup=build_draft_menu(uid))

@Client.on_callback_query(filters.regex(r"^wiz_(?P<action>[a-z_]+)_(?P<uid>\d+)$"))
async def draft_actions(client, query):
    action = query.matches[0].group("action")
    uid = int(query.matches[0].group("uid"))
    draft = DRAFTS.get(uid)
    
    if action == "cancel":
        del DRAFTS[uid]
        await query.message.edit_text("🗑 Draft deleted.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="dash_main")]]))
        
    elif action == "sig":
        draft["use_sig"] = not draft["use_sig"]
        await query.message.edit_reply_markup(reply_markup=build_draft_menu(uid))
        
    elif action == "btn":
        await query.message.reply("🔗 **Add URL Button**\nReply with: `Button Name - https://link.com`", reply_markup=ForceReply(selective=True))
        
    elif action == "reac":
        if draft["reactions"]:
            draft["reactions"] = [] # Clear if already set
            await query.message.edit_reply_markup(reply_markup=build_draft_menu(uid))
        else:
            await query.message.reply("👍 **Custom Reactions**\nReply with emojis separated by spaces (e.g., `👍 ❤️ 😂`)", reply_markup=ForceReply(selective=True))
            
    elif action == "publish":
        ch_data = await get_channel(draft["chat_id"])
        
        # 1. Append Signature if requested
        final_text = draft["text"]
        if draft["use_sig"] and ch_data.get("signature"):
            final_text += f"\n\n{ch_data['signature']}"
            
        # 2. Build URL Buttons
        kb = [[InlineKeyboardButton(b["text"], url=b["url"])] for b in draft["buttons"]]
        
        # 3. Send Post
        markup = InlineKeyboardMarkup(kb) if kb else None
        try:
            if draft["media_type"] == "photo":
                msg = await client.send_photo(draft["chat_id"], photo=draft["media_id"], caption=final_text, reply_markup=markup)
            elif draft["media_type"] == "video":
                msg = await client.send_video(draft["chat_id"], video=draft["media_id"], caption=final_text, reply_markup=markup)
            else:
                msg = await client.send_message(draft["chat_id"], text=final_text, reply_markup=markup)
            
            # 4. Determine which emojis to use (Custom vs Default)
            emojis = draft["reactions"] if draft["reactions"] else ch_data.get("default_reactions", [])
            
            if emojis:
                post_id = await create_live_post(draft["chat_id"], msg.id, emojis)
                reac_row = [InlineKeyboardButton(f"{e} 0", callback_data=f"react_{post_id}_{e}") for e in emojis]
                kb.append(reac_row)
                await msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(kb))
                
            await query.message.edit_text("🚀 **Post Published!**")
            del DRAFTS[uid]
        except Exception as e:
            await query.answer(f"Error: {e}", show_alert=True)

#+&7&7&+&+



@Client.on_callback_query(filters.regex(r"^react_(?P<post_id>[0-9a-fA-F]{24})_(?P<emoji>.+)$"))
async def handle_reaction(client, query):
    post_id = query.matches[0].group("post_id")
    emoji = query.matches[0].group("emoji")
    user_id = query.from_user.id
    
    updated_post = await update_reaction(post_id, emoji, user_id)
    if not updated_post:
        return await query.answer("Post expired.", show_alert=True)
    
    existing_kb = query.message.reply_markup.inline_keyboard
    new_kb = []
    
    # Keep original URL buttons
    for row in existing_kb:
        if not row[0].callback_data or not row[0].callback_data.startswith("react_"):
            new_kb.append(row)
            
    # Rebuild Reaction Row with live counts
    reac_row = []
    for emj, users in updated_post["reactions"].items():
        count = len(users)
        count_str = f" {count}" if count > 0 else " 0"
        reac_row.append(InlineKeyboardButton(f"{emj}{count_str}", callback_data=f"react_{post_id}_{emj}"))
    
    new_kb.append(reac_row)
    
    try:
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_kb))
        await query.answer("Reacted!")
    except Exception:
        await query.answer() # Fails silently if they click too fast



#&+_+&(&(&(&(-(-(-


# --- Auto Complete / Signature for Manual Posts ---
@Client.on_message(filters.channel & ~filters.edited)
async def auto_complete_handler(client, message):
    # Ignore messages sent by the bot itself (the wizard handles those)
    if message.from_user and message.from_user.is_self: return
    
    ch_data = await get_channel(message.chat.id)
    if not ch_data: return
    
    append_text = ch_data.get("auto_complete", "")
    if append_text:
        try:
            if message.caption:
                await message.edit_caption(f"{message.caption.html}\n\n{append_text}")
            elif message.text:
                await message.edit_text(f"{message.text.html}\n\n{append_text}")
        except Exception:
            pass

# --- Welcome Approvals ---
@Client.on_chat_join_request()
async def welcome_approver(client, message):
    ch_data = await get_channel(message.chat.id)
    if ch_data and ch_data.get("welcome_enabled"):
        await client.approve_chat_join_request(message.chat.id, message.from_user.id)
        try:
            await client.send_message(message.from_user.id, f"Welcome to **{message.chat.title}**! 🎉")
        except:
            pass
