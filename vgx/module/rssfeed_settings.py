from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.rss_db import db

# --- HELPERS ---

async def get_manage_keyboard(chat_id, feed):
    """Helper to rebuild the keyboard based on current DB state"""
    tgl_preview = "✅" if feed['preview_enabled'] else "❌"
    tgl_notif = "✅" if feed['notifications_enabled'] else "❌"
    tgl_active = "✅ Active" if feed['is_active'] else "❌ Paused"
    mode = feed['parse_mode'].upper()

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Status: {tgl_active}", callback_data=f"tgl_is_active_{chat_id}")],
        [
            InlineKeyboardButton(f"Previews: {tgl_preview}", callback_data=f"tgl_preview_enabled_{chat_id}"),
            InlineKeyboardButton(f"Notifs: {tgl_notif}", callback_data=f"tgl_notifications_enabled_{chat_id}")
        ],
        [InlineKeyboardButton(f"Parse Mode: {mode}", callback_data=f"tgl_parse_mode_{chat_id}")],
        [InlineKeyboardButton("🧹 Clear Cache (Repost all)", callback_data=f"clear_{chat_id}")]
    ])

# --- HANDLERS ---

@Client.on_callback_query(filters.regex(r"^manage_(-?\ dropped\d+)$"))
async def manage_menu(client, query: CallbackQuery):
    chat_id = int(query.matches[0].group(1))
    feeds = await db.get_chat_feeds(chat_id)
    
    if not feeds:
        return await query.answer("No feeds found for this chat.", show_alert=True)
        
    feed = feeds[0]
    markup = await get_manage_keyboard(chat_id, feed)
    
    await query.message.edit_text(
        f"**Settings for feed:**\n`{feed['feed_url']}`", 
        reply_markup=markup
    )

@Client.on_callback_query(filters.regex(r"^tgl_(?P<setting>\w+)_(-?\d+)$"))
async def toggle_settings(client, query: CallbackQuery):
    setting = query.matches[0].group("setting")
    chat_id = int(query.matches[0].group(2))
    
    feeds = await db.get_chat_feeds(chat_id)
    if not feeds:
        return await query.answer("Feed not found.")
        
    feed = feeds[0]
    url = feed['feed_url']
    
    # Toggle logic
    if setting == "parse_mode":
        new_val = "markdown" if feed['parse_mode'] == "html" else "html"
    else:
        # Dynamic boolean toggle (is_active, preview_enabled, etc)
        new_val = not feed.get(setting, False)
        
    await db.update_feed_setting(chat_id, url, setting, new_val)
    
    # Refresh the UI by fetching updated data
    updated_feeds = await db.get_chat_feeds(chat_id)
    markup = await get_manage_keyboard(chat_id, updated_feeds[0])
    
    await query.message.edit_reply_markup(reply_markup=markup)
    await query.answer("Setting updated!")

@Client.on_callback_query(filters.regex(r"^clear_(-?\d+)$"))
async def clear_feed_cache(client, query: CallbackQuery):
    chat_id = int(query.matches[0].group(1))
    feeds = await db.get_chat_feeds(chat_id)
    
    if feeds:
        url = feeds[0]['feed_url']
        await db.clear_cache(chat_id, url)
        await query.answer("🔥 Cache cleared! All entries will be reposted.", show_alert=True)
    else:
        await query.answer("Error: Feed not found.")
