from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

async def build_kb(feed):
    fid = str(feed["_id"])
    t_act = "✅ On" if feed['is_active'] else "❌ Off"
    t_prv = "✅" if feed['preview_enabled'] else "❌"
    t_img = "✅" if feed['images_enabled'] else "❌"
    t_not = "✅" if feed['notifications_enabled'] else "❌"
    mode = feed['parse_mode'].upper()

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Active: {t_act}", callback_data=f"tgl_is_active_{fid}")],
        [
            InlineKeyboardButton(f"Previews: {t_prv}", callback_data=f"tgl_preview_enabled_{fid}"),
            InlineKeyboardButton(f"Images: {t_img}", callback_data=f"tgl_images_enabled_{fid}")
        ],
        [
            InlineKeyboardButton(f"Notifs: {t_not}", callback_data=f"tgl_notifications_enabled_{fid}"),
            InlineKeyboardButton(f"Mode: {mode}", callback_data=f"tgl_parse_mode_{fid}")
        ],
        [InlineKeyboardButton("📝 Change Message Format", callback_data=f"ask_template_{fid}")],
        [InlineKeyboardButton("🔗 Change Feed URL", callback_data=f"ask_url_{fid}")],
        [InlineKeyboardButton("🧹 Clear Cache", callback_data=f"act_clear_{fid}")],
        [InlineKeyboardButton("🗑 Delete Source", callback_data=f"act_delete_{fid}")]
    ])

@Client.on_callback_query(filters.regex(r"^manage_(?P<feed_id>\w+)$"))
async def manage_menu(client, query: CallbackQuery):
    feed_id = query.matches[0].group("feed_id")
    feed = await client.db.get_feed(feed_id)
    
    if not feed:
        return await query.answer("Feed deleted.", show_alert=True)
        
    markup = await build_kb(feed)
    await query.message.edit_text(f"**Settings for:** `{feed['feed_url']}`", reply_markup=markup)

@Client.on_callback_query(filters.regex(r"^tgl_(?P<setting>\w+)_(?P<feed_id>\w+)$"))
async def toggles(client, query: CallbackQuery):
    setting = query.matches[0].group("setting")
    feed_id = query.matches[0].group("feed_id")
    feed = await client.db.get_feed(feed_id)
    
    if setting == "parse_mode":
        new_val = "markdown" if feed['parse_mode'] == "html" else "html"
    else:
        new_val = not feed.get(setting, False)
        
    await client.db.update_setting(feed_id, setting, new_val)
    updated_feed = await client.db.get_feed(feed_id)
    
    await query.message.edit_reply_markup(reply_markup=await build_kb(updated_feed))
    await query.answer("Setting Updated")

@Client.on_callback_query(filters.regex(r"^act_(?P<action>\w+)_(?P<feed_id>\w+)$"))
async def actions(client, query: CallbackQuery):
    action, feed_id = query.matches[0].group("action"), query.matches[0].group("feed_id")
    if action == "clear":
        await client.db.clear_cache(feed_id)
        await query.answer("Cache Cleared! Reposting latest.", show_alert=True)
    elif action == "delete":
        await client.db.delete_feed(feed_id)
        await query.message.edit_text("🗑 Source Deleted.")

@Client.on_callback_query(filters.regex(r"^ask_(?P<action>\w+)_(?P<feed_id>\w+)$"))
async def ask_input(client, query: CallbackQuery):
    action, feed_id = query.matches[0].group("action"), query.matches[0].group("feed_id")
    
    # Save the user's state so we know what they are replying to
    client.user_states[query.from_user.id] = {"action": action, "feed_id": feed_id}
    
    text = "Send me the new message template containing placeholders like `{{title}}`:" if action == "template" else "Send me the new RSS URL:"
    await query.message.reply_text(f"✏️ {text}\n*(Send /cancel to abort)*")
    await query.answer()
