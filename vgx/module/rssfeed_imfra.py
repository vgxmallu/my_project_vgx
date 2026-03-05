from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from vgx.database.rssfeed_db import db, get_feeds, add_feed, update_feed, clear_cache
from bson.objectid import ObjectId

# --- UI Helpers ---
def build_feed_menu(feed: dict):
    fid = str(feed["_id"])
    btn_state = "🟢 Enabled" if feed.get("enabled") else "🔴 Disabled"
    btn_fmt = f"📝 Format: {feed.get('format', 'Markdown')}"
    btn_img = "🖼 Images: ON" if feed.get("send_images") else "🖼 Images: OFF"
    btn_prev = "🔗 Preview: ON" if feed.get("link_preview") else "🔗 Preview: OFF"
    btn_notif = "🔕 Notify: OFF" if feed.get("silent_notification") else "🔔 Notify: ON"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_state, callback_data=f"rss_tgl_enabled_{fid}"),
         InlineKeyboardButton(btn_fmt, callback_data=f"rss_tgl_format_{fid}")],
        [InlineKeyboardButton(btn_img, callback_data=f"rss_tgl_img_{fid}"),
         InlineKeyboardButton(btn_prev, callback_data=f"rss_tgl_prev_{fid}")],
        [InlineKeyboardButton(btn_notif, callback_data=f"rss_tgl_notif_{fid}")],
        [InlineKeyboardButton("✏️ Edit Template", callback_data=f"rss_req_template_{fid}"),
         InlineKeyboardButton("🔄 Clear Cache", callback_data=f"rss_cmd_clear_{fid}")],
        [InlineKeyboardButton("🗑 Delete Source", callback_data=f"rss_cmd_delete_{fid}")]
    ])

# --- 1. Main Command ---
@Client.on_message(filters.command("rss") & filters.private)
async def rss_start(client, message):
    await message.reply("⚙️ **RSS Manager**\nUse `/addfeed <chat_id>` to connect a new RSS source to a group or channel.")

# --- 2. Add Feed via Command ---
@Client.on_message(filters.command("addfeed") & filters.private)
async def cmd_addfeed(client, message):
    if len(message.command) == 1:
        return await message.reply("❌ Usage: `/addfeed -100123456789`")
    
    chat_id = int(message.command[1])
    # Force the user to reply to this specific message with their URL
    await message.reply(
        f"🔗 **Adding Feed for {chat_id}**\n\nPlease reply to this message with a valid RSS or ATOM Feed URL.",
        reply_markup=ForceReply(selective=True)
    )

# --- 3. Handle Forced Replies (New URL or New Template) ---
@Client.on_message(filters.reply & filters.private)
async def handle_replies(client, message):
    original_text = message.reply_to_message.text
    
    if "Adding Feed for" in original_text:
        chat_id = int(original_text.split()[4])
        url = message.text.strip()
        await add_feed(chat_id, url)
        await message.reply(f"✅ Feed added successfully!\nURL: `{url}`\nUse `/manage {chat_id}` to configure it.")
        
    elif "Editing Template for" in original_text:
        feed_id = original_text.split("\n")[-1].replace("ID: ", "").strip()
        new_template = message.text
        await update_feed(ObjectId(feed_id), template=new_template)
        await message.reply("✅ Custom template saved successfully!")

# --- 4. Manage Command ---
@Client.on_message(filters.command("manage") & filters.private)
async def cmd_manage(client, message):
    if len(message.command) == 1: return await message.reply("❌ Usage: `/manage <chat_id>`")
    
    chat_id = int(message.command[1])
    feeds = await get_feeds(chat_id)
    if not feeds: return await message.reply("⚠️ No feeds found for this chat.")
    
    for feed in feeds:
        text = f"📡 **Feed Source:** `{feed['url']}`\n🎯 **Target:** `{feed['chat_id']}`"
        await message.reply(text, reply_markup=build_feed_menu(feed))

# --- 5. Regex Callbacks ---
@Client.on_callback_query(filters.regex(r"^rss_(?P<action>tgl|req|cmd)_(?P<param>[a-z_]+)_(?P<fid>[0-9a-fA-F]{24})$"))
async def rss_callbacks(client, query):
    action = query.matches[0].group("action")
    param = query.matches[0].group("param")
    fid_str = query.matches[0].group("fid")
    fid = ObjectId(fid_str)
    
    feed = await db.feeds.find_one({"_id": fid})
    if not feed: return await query.answer("Feed deleted.", show_alert=True)
    
    if action == "tgl":
        if param == "enabled": await update_feed(fid, enabled=not feed.get("enabled"))
        elif param == "format": await update_feed(fid, format="HTML" if feed.get("format") == "Markdown" else "Markdown")
        elif param == "img": await update_feed(fid, send_images=not feed.get("send_images"))
        elif param == "prev": await update_feed(fid, link_preview=not feed.get("link_preview"))
        elif param == "notif": await update_feed(fid, silent_notification=not feed.get("silent_notification"))
        
        feed = await db.feeds.find_one({"_id": fid})
        await query.message.edit_reply_markup(reply_markup=build_feed_menu(feed))
        
    elif action == "req" and param == "template":
        await query.message.reply(
            f"✏️ **Editing Template for Feed**\nReply to this message with your new template using placeholders like `{{title}}`.\n\nID: `{fid_str}`",
            reply_markup=ForceReply(selective=True)
        )
        
    elif action == "cmd":
        if param == "clear":
            await clear_cache(fid)
            await query.answer("🔄 Cache cleared! Old posts will resend on next cycle.", show_alert=True)
        elif param == "delete":
            await db.feeds.delete_one({"_id": fid})
            await query.message.delete()
