import aiohttp

API_BASE = "https://iptv-org.github.io/api"

async def fetch_iptv_data(endpoint: str) -> list:
    """Fetches public JSON data from official iptv-org api repositories."""
    url = f"{API_BASE}/{endpoint}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return []

#====================================================
import aiohttp
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from vgx.database.iptv_db import db

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


@Client.on_message(filters.command("iptv") & filters.private)
async def iptv_home(client: Client, message: Message):
    text = (
        "📺 **Welcome to IPTV-Org Global Hub!**\n\n"
        "Explore thousands of free public global channels, live streams, and program guides.\n"
        "Select an option below to browse:"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌍 Browse Countries", callback_data="iptv_countries"),
            InlineKeyboardButton("📂 Browse Categories", callback_data="iptv_categories")
        ],
        [
            InlineKeyboardButton("📡 Check Stream Health", callback_data="iptv_health_status")
        ]
    ])
    await message.reply_text(text, reply_markup=keyboard)

@Client.on_message(filters.command("sync") & filters.private)
async def sync_database(client: Client, message: Message):
    msg = await message.reply_text("🔄 Syncing core data from iptv-org APIs...")
    
    channels = await fetch_iptv_data("channels.json")
    if channels:
        await db.channels.delete_many({})
        await db.channels.insert_many(channels)
        
    streams = await fetch_iptv_data("streams.json")
    if streams:
        await db.streams.delete_many({})
        await db.streams.insert_many(streams)
        
    guides = await fetch_iptv_data("guides.json")
    if guides:
        await db.guides.delete_many({})
        await db.guides.insert_many(guides)
        
    await msg.edit_text(
        f"✅ **Sync Complete!**\n"
        f"• Channels cached: `{len(channels)}`\n"
        f"• Streams cached: `{len(streams)}`\n"
        f"• EPG Guides cached: `{len(guides)}`"
    )

#====================================================

@Client.on_callback_query(filters.regex(r"^iptv_home$"))
async def cb_home(client: Client, query: CallbackQuery):
    text = (
        "📺 **Welcome to IPTV-Org Global Hub!**\n\n"
        "Explore thousands of free public global channels, live streams, and program guides.\n"
        "Select an option below to browse:"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌍 Browse Countries", callback_data="iptv_countries"),
            InlineKeyboardButton("📂 Browse Categories", callback_data="iptv_categories")
        ],
        [
            InlineKeyboardButton("📡 Check Stream Health", callback_data="iptv_health_status")
        ]
    ])
    await query.message.edit_text(text, reply_markup=keyboard)
    await query.answer()

@Client.on_callback_query(filters.regex(r"^iptv_countries$"))
async def cb_countries(client: Client, query: CallbackQuery):
    await query.answer("Loading countries...")
    countries = await fetch_iptv_data("countries.json")
    
    keyboard = []
    row = []
    for c in countries[:50]:
        row.append(InlineKeyboardButton(f"{c.get('flag', '🌐')} {c['name']}", callback_data=f"iptv_cc_{c['code']}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="iptv_home")])
    
    await query.message.edit_text(
        "🌍 **Select a Country:**\nChoose a region to list available public broadcasts.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@Client.on_callback_query(filters.regex(r"^iptv_cc_([A-Z]{2})$"))
async def cb_country_channels(client: Client, query: CallbackQuery):
    cc = query.matches[0].group(1)
    await query.answer(f"Fetching channels for {cc}...")
    
    cursor = db.channels.find({"country": cc}).limit(10)
    channels = await cursor.to_list(length=None)
    
    if not channels:
        return await query.edit_message_text(
            f"❌ No channels found for country code `{cc}`.\nMake sure you ran `/sync` first!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="iptv_countries")]])
        )
        
    keyboard = []
    for ch in channels:
        keyboard.append([InlineKeyboardButton(f"📺 {ch['name']}", callback_data=f"iptv_chn_{ch['id']}")])
        
    keyboard.append([InlineKeyboardButton("🔙 Back to Countries", callback_data="iptv_countries")])
    
    await query.message.edit_text(
        f"📡 **Channels in Country (`{cc}`):**\nSelect a channel to get stream links & EPG schedule:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@Client.on_callback_query(filters.regex(r"^iptv_categories$"))
async def cb_categories(client: Client, query: CallbackQuery):
    await query.answer("Loading categories...")
    categories = await fetch_iptv_data("categories.json")
    
    keyboard = []
    row = []
    for cat in categories[:20]:
        row.append(InlineKeyboardButton(f"📂 {cat['name']}", callback_data=f"iptv_cat_{cat['id']}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="iptv_home")])
    
    await query.message.edit_text(
        "📂 **Select a Genre / Category:**",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@Client.on_callback_query(filters.regex(r"^iptv_cat_([a-z0-9_-]+)$"))
async def cb_category_channels(client: Client, query: CallbackQuery):
    cat_id = query.matches[0].group(1)
    await query.answer("Loading category channels...")
    
    cursor = db.channels.find({"categories": cat_id}).limit(10)
    channels = await cursor.to_list(length=None)
    
    if not channels:
        return await query.edit_message_text(
            f"❌ No channels found in category `{cat_id}`.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="iptv_categories")]])
        )
        
    keyboard = []
    for ch in channels:
        keyboard.append([InlineKeyboardButton(f"📺 {ch['name']}", callback_data=f"iptv_chn_{ch['id']}")])
        
    keyboard.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="iptv_categories")])
    
    await query.message.edit_text(
        f"📂 **Category: `{cat_id}`**\nSelect a channel:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@Client.on_callback_query(filters.regex(r"^iptv_chn_(.+)$"))
async def cb_channel_details(client: Client, query: CallbackQuery):
    ch_id = query.matches[0].group(1)
    await query.answer("Fetching channel streams & guide info...")
    
    channel = await db.channels.find_one({"id": ch_id})
    stream = await db.streams.find_one({"channel": ch_id})
    guide = await db.guides.find_one({"channel": ch_id})
    
    if not channel:
        return await query.answer("Channel info not found!", show_alert=True)
        
    name = channel.get("name", "Unknown")
    country = channel.get("country", "N/A")
    website = channel.get("website", "Not available")
    stream_url = stream.get("url") if stream else None
    
    text = (
        f"📺 **Channel Details:** `{name}`\n\n"
        f"🌐 **Country:** `{country}`\n"
        f"🔗 **Website:** {website}\n"
    )
    
    if stream_url:
        text += f"\n▶️ **Stream URL:**\n`{stream_url}`\n"
    else:
        text += f"\n⚠️ *No active stream link mapped in database.*\n"
        
    if guide:
        text += f"🗓 **EPG Source Site:** `{guide.get('site', 'N/A')}` (`{guide.get('site_id', '')}`)\n"
        
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="iptv_home")]
    ])
    
    await query.message.edit_text(text, reply_markup=keyboard)

@Client.on_callback_query(filters.regex(r"^iptv_health_status$"))
async def cb_health_status(client: Client, query: CallbackQuery):
    await query.answer("Checking system health cache...")
    count = await db.health_logs.count_documents({"status": "offline"})
    total = await db.health_logs.count_documents({})
    
    text = (
        "📡 **Stream Health Monitor Status**\n\n"
        f"• Total Checked Streams: `{total}`\n"
        f"• Flagged Offline/Unstable: `{count}`\n\n"
        "Background scheduler runs checks periodically."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="iptv_home")]
    ])
    await query.message.edit_text(text, reply_markup=keyboard)

#====================================================


logger = logging.getLogger("IPTVHealthMonitor")

async def test_streams_job(client):
    """Background worker that periodically checks stream URL availability."""
    logger.info("🔍 Running stream health check worker...")
    
    cursor = db.streams.find({}).limit(20)
    streams = await cursor.to_list(length=None)
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        for s in streams:
            url = s.get("url")
            channel = s.get("channel")
            if not url:
                continue
                
            status = "online"
            try:
                async with session.get(url) as resp:
                    if resp.status >= 400:
                        status = "offline"
            except Exception:
                status = "offline"
                
            await db.health_logs.update_one(
                {"channel": channel, "url": url},
                {"$set": {"status": status}},
                upsert=True
            )

def start_iptv_monitor(app, scheduler: AsyncIOScheduler):
    """Schedules the stream health check worker every 2 hours."""
    scheduler.add_job(
        test_streams_job,
        "interval",
        hours=2,
        args=[app],
        id="iptv_health_monitor",
        replace_existing=True
    )
