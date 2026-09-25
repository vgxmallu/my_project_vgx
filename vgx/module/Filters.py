
import re
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.filter_db import db
from pyrogram.types import Message

 


def format_placeholders(text: str, message) -> str:
    """Replaces dynamic placeholders with actual user/chat data."""
    if not text:
        return text
        
    user = message.from_user
    chat = message.chat
    
    if user:
        text = text.replace("{first_name}", user.first_name or "")
        text = text.replace("{last_name}", user.last_name or "")
        text = text.replace("{username}", f"@{user.username}" if user.username else "")
        text = text.replace("{user_id}", str(user.id))
        text = text.replace("{mention}", user.mention)
    if chat:
        text = text.replace("{chatname}", chat.title or chat.first_name or "")
        
    return text

def serialize_markup(markup):
    """Converts Pyrogram InlineKeyboardMarkup into a dictionary list for MongoDB."""
    if not markup or not getattr(markup, "inline_keyboard", None):
        return None
    
    keyboard = []
    for row in markup.inline_keyboard:
        btn_row = []
        for btn in row:
            btn_row.append({
                "text": btn.text, 
                "url": btn.url, 
                "callback_data": btn.callback_data
            })
        keyboard.append(btn_row)
    return keyboard

def deserialize_markup(kb_list):
    """Rebuilds Pyrogram InlineKeyboardMarkup from MongoDB data."""
    if not kb_list:
        return None
        
    keyboard = []
    for row in kb_list:
        btn_row = []
        for btn in row:
            btn_row.append(
                InlineKeyboardButton(
                    text=btn["text"], 
                    url=btn.get("url"), 
                    callback_data=btn.get("callback_data")
                )
            )
        keyboard.append(btn_row)
    return InlineKeyboardMarkup(keyboard)



@Client.on_message(filters.command(["filter", "mfilter"]) & filters.group)
async def save_filter(client: Client, message: Message):
    args = message.text.split(None, 2)
    if len(args) < 2 and not message.reply_to_message:
        return await message.reply_text("Usage: `/filter keyword response` or reply to a message with `/filter keyword`")

    keyword = args[1].lower()
    chat_id = message.chat.id
    reply = message.reply_to_message

    filter_data = {
        "chat_id": chat_id,
        "keyword": keyword,
        "media_type": "text",
        "file_id": None,
        "text": None,
        "markup": None
    }

    # Handle Replied Messages (Media + Text + Buttons)
    if reply:
        filter_data["markup"] = serialize_markup(reply.reply_markup)
        
        if reply.text:
            filter_data["text"] = reply.text
        elif reply.caption:
            filter_data["text"] = reply.caption

        if reply.photo:
            filter_data["media_type"] = "photo"
            filter_data["file_id"] = reply.photo.file_id
        elif reply.document:
            filter_data["media_type"] = "document"
            filter_data["file_id"] = reply.document.file_id
        elif reply.video:
            filter_data["media_type"] = "video"
            filter_data["file_id"] = reply.video.file_id
        elif reply.animation:
            filter_data["media_type"] = "animation"
            filter_data["file_id"] = reply.animation.file_id
        elif reply.audio:
            filter_data["media_type"] = "audio"
            filter_data["file_id"] = reply.audio.file_id
        elif reply.sticker:
            filter_data["media_type"] = "sticker"
            filter_data["file_id"] = reply.sticker.file_id
            
    # Handle Inline Text Creation
    else:
        if len(args) < 3:
            return await message.reply_text("You must provide text or reply to a message!")
        filter_data["text"] = args[2]

    # Save to MongoDB
    await db.filters.update_one(
        {"chat_id": chat_id, "keyword": keyword},
        {"$set": filter_data},
        upsert=True
    )
    await message.reply_text(f"✅ Filter **{keyword}** has been saved!")

@Client.on_message(filters.command("stop") & filters.group)
async def stop_filter(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text("Usage: `/stop keyword`")

    keyword = args[1].lower()
    result = await db.filters.delete_one({"chat_id": message.chat.id, "keyword": keyword})
    
    if result.deleted_count > 0:
        await message.reply_text(f"🗑 Filter **{keyword}** deleted.")
    else:
        await message.reply_text(f"❌ Filter **{keyword}** not found.")

@Client.on_message(filters.command("filters") & filters.group)
async def list_filters(client: Client, message: Message):
    cursor = db.filters.find({"chat_id": message.chat.id})
    filter_list = await cursor.to_list(length=None)
    
    if not filter_list:
        return await message.reply_text("No active filters in this chat.")
        
    text = "📝 **Active Filters:**\n"
    for f in filter_list:
        text += f"✧ `{f['keyword']}`\n"
        
    await message.reply_text(text)

@Client.on_message(filters.command("stopall") & filters.group)
async def stopall_filters(client: Client, message: Message):
    # Sends a UI confirmation using InlineKeyboardButtons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data="stopall_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="stopall_cancel")
        ]
    ])
    await message.reply_text(
        "⚠️ **Are you sure you want to delete ALL filters in this chat?**",
        reply_markup=keyboard
    )


#====================================================

@Client.on_callback_query(filters.regex(r"^stopall_(confirm|cancel)$"))
async def stopall_callback(client: Client, query: CallbackQuery):
    action = query.matches[0].group(1)
    
    if action == "cancel":
        await query.message.delete()
        await query.answer("Stopall cancelled.", show_alert=False)
        return

    if action == "confirm":
        chat_id = query.message.chat.id
        await db.filters.delete_many({"chat_id": chat_id})
        
        await query.message.edit_text("🗑 **All filters have been successfully deleted.**")
        await query.answer("Filters cleared!")


@Client.on_message(filters.group & filters.text & ~filters.bot, group=1)
async def filter_watcher(client: Client, message: Message):
    text = message.text.lower()
    
    # Fetch all filters for this specific chat
    cursor = db.filters.find({"chat_id": message.chat.id})
    chat_filters = await cursor.to_list(length=None)
    
    for f in chat_filters:
        keyword = f["keyword"]
        
        # Matches the exact word boundary so "hi" doesn't trigger on "this"
        if re.search(r'\b' + re.escape(keyword) + r'\b', text):
            
            # Format text placeholders
            reply_text = format_placeholders(f.get("text"), message)
            
            # Reconstruct inline keyboards if they were saved
            reply_markup = deserialize_markup(f.get("markup"))
            
            # Dispatch based on media type
            m_type = f.get("media_type")
            file_id = f.get("file_id")
            
            if m_type == "text":
                await message.reply_text(reply_text, reply_markup=reply_markup, disable_web_page_preview=True)
            elif m_type == "photo":
                await message.reply_photo(file_id, caption=reply_text, reply_markup=reply_markup)
            elif m_type == "document":
                await message.reply_document(file_id, caption=reply_text, reply_markup=reply_markup)
            elif m_type == "video":
                await message.reply_video(file_id, caption=reply_text, reply_markup=reply_markup)
            elif m_type == "animation":
                await message.reply_animation(file_id, caption=reply_text, reply_markup=reply_markup)
            elif m_type == "audio":
                await message.reply_audio(file_id, caption=reply_text, reply_markup=reply_markup)
            elif m_type == "sticker":
                await message.reply_sticker(file_id, reply_markup=reply_markup)
                
            break  # Stop checking after the first successful filter match
