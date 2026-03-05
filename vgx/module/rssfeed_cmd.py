from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from vgx.database.rssfeed_db import db, get_feeds, add_feed, update_feed, clear_cache
from bson.objectid import ObjectId
from pyrogram.enums import ButtonStyle

# --- UI Helpers ---
def build_feed_menu(feed: dict):
    fid = str(feed["_id"])
    btn_state = "🟢 Enabled" if feed.get("enabled") else "🔴 Disabled"
    btn_fmt = f"📝 Format: {feed.get('format', 'Markdown')}"
    btn_img = "🖼 Images: ON" if feed.get("send_images") else "🖼 Images: OFF"
    btn_prev = "🔗 Preview: ON" if feed.get("link_preview") else "🔗 Preview: OFF"
    btn_notif = "🔕 Notify: OFF" if feed.get("silent_notification") else "🔔 Notify: ON"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_state, callback_data=f"rss_tgl_enabled_{fid}", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton(btn_fmt, callback_data=f"rss_tgl_format_{fid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(btn_img, callback_data=f"rss_tgl_img_{fid}", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton(btn_prev, callback_data=f"rss_tgl_prev_{fid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(btn_notif, callback_data=f"rss_tgl_notif_{fid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("✏️ Edit Template", callback_data=f"rss_req_template_{fid}", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton("🔄 Clear Cache", callback_data=f"rss_cmd_clear_{fid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("🗑 Delete Source", callback_data=f"rss_cmd_delete_{fid}", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel", style=ButtonStyle.DANGER)]
    ])

# --- 1. Main Command ---
@Client.on_message(filters.command("rss"))
async def rss_sthsart(client, message):
    await message.reply("⚙️ **RSS Manager**\nUse `/addfeed <chat_id>` to connect a new RSS source to a group or channel.\n⚠️ Hey Im only working with PM!")

# --- 2. Add Feed via Command ---
@Client.on_message(filters.command("addfeed") & filters.private) #& filters.private
async def cmd_addfedhed(client, message):
    if len(message.command) == 1:
        return await message.reply("❌ Usage: `/addfeed -100123456789`")
    
    chat_id = int(message.command[1])
    # Force the user to reply to this specific message with their URL
    await message.reply(
        f"🔗 **Adding Feed for {chat_id}**\n\nPlease reply to this message with a valid RSS or ATOM Feed URL.",
        reply_markup=ForceReply(selective=True)
    )
    
"""
# --- 3. Handle Forced Replies (New URL or New Template) ---
@Client.on_message(filters.reply & filters.private)
async def handle_hdreplies(client, message):
    original_text = message.reply_to_message.text
    
    if "Adding Feed for" in original_text:
        chat_id = int(original_text.split()[4])
        url = message.text.strip()
        await add_feed(chat_id, url)
        await message.reply(f"✅ Feed added successfully!\nURL: `{url}`\nUse `/managerss {chat_id}` to configure it.")
        
    elif "Editing Template for" in original_text:
        feed_id = original_text.split("\n")[-1].replace("ID: ", "").strip()
        new_template = message.text
        await update_feed(ObjectId(feed_id), template=new_template)
        await message.reply("✅ Custom template saved successfully!")
"""


from vgx.database.rssfeed_db import count_feeds # Don't forget to import the new function!
@Client.on_message(filters.reply & filters.private)
async def handle_replies(client, message):
    original_text = message.reply_to_message.text
    
    if "Adding Feed for" in original_text:
        chat_id = int(original_text.split()[4])
        
        # 1. Split the user's message by spaces or newlines to find all URLs
        raw_urls = message.text.strip().split()
        
        # 2. Check how many feeds the group ALREADY has
        current_count = await count_feeds(chat_id)
        
        # 3. Calculate if this new batch pushes them over the limit
        if current_count + len(raw_urls) > 5:
            return await message.reply(
                f"❌ **Limit Reached!**\n"
                f"This group already has {current_count} feeds. You can only have a maximum of 5 feeds per group.\n"
                f"Please send fewer links or delete old feeds using `/managerss {chat_id}`."
            )

        # 4. Loop through and add every URL they sent
        added_urls = []
        for url in raw_urls:
            # Simple validation to ensure it looks like a URL
            if url.startswith("http://") or url.startswith("https://"):
                await add_feed(chat_id, url)
                added_urls.append(url)
            
        if not added_urls:
            return await message.reply("⚠️ No valid URLs found. Make sure they start with http:// or https://")

        # 5. Send a success summary
        summary = "\n".join([f"✅ `{u}`" for u in added_urls])
        await message.reply(
            f"🎉 **Successfully added {len(added_urls)} feed(s)!**\n\n{summary}\n\n"
            f"Use `/managerss {chat_id}` to configure their templates."
        )

@Client.on_message(filters.command(["managerss", "manage"]) & filters.private)
async def cmd_manage(client, message):
    if len(message.command) == 1: 
        return await message.reply("❌ **Usage:** `/managerss -100123456789`")
    
    try:
        chat_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ **Invalid Chat ID.** Please provide a valid numeric ID.")
        
    feeds = await get_feeds(chat_id)
    if not feeds: 
        return await message.reply(f"⚠️ No feeds found for `{chat_id}`.\nUse `/addfeed {chat_id}` to add one!")
    
    # --- 1. The Summary Header ---
    feed_count = len(feeds)
    await message.reply(
        f"📊 **RSS Manager for Target:** `{chat_id}`\n\n"
        f"📈 **Quota Used:** {feed_count} / 5 Feeds\n"
        "👇 *Here are your connected sources:*"
    )
    
    # --- 2. Send the Individual Menus ---
    for feed in feeds:
        text = (
            f"📡 **Source:** `{feed['url']}`\n"
            f"🎯 **Target:** `{feed['chat_id']}`"
        )
        await message.reply(text, reply_markup=build_feed_menu(feed))



"""
# --- 4. Manage Command ---
@Client.on_message(filters.command("managerss") & filters.private)
async def cmd_mandhage(client, message):
    if len(message.command) == 1: return await message.reply("❌ Usage: `/managerss <chat_id>`")
    
    chat_id = int(message.command[1])
    feeds = await get_feeds(chat_id)
    if not feeds: return await message.reply("⚠️ No feeds found for this chat.")
    
    for feed in feeds:
        text = f"📡 **Feed Source:** `{feed['url']}`\n🎯 **Target:** `{feed['chat_id']}`"
        await message.reply(text, reply_markup=build_feed_menu(feed))
"""
# --- 5. Regex Callbacks ---
@Client.on_callback_query(filters.regex(r"^rss_(?P<action>tgl|req|cmd)_(?P<param>[a-z_]+)_(?P<fid>[0-9a-fA-F]{24})$"))
async def rss_cdallbacks(client, query):
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
