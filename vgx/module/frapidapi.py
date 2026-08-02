import aiohttp
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified
from config import Config
# Credentials mapped directly from your provided snippet
HEADERS = {
    "x-rapidapi-key": "2170275bfemsh6eb2ff11d740b03p1706ebjsnff878dca22c0",
    "x-rapidapi-host": "sportapi7.p.rapidapi.com",
    "Content-Type": "application/json"
}
BASE_URL = "https://sportapi7.p.rapidapi.com/api/v1"

async def fetch_scheduled_events(date_str: str = None):
    """
    Fetches scheduled events for Category 1 (Football).
    Defaults to today's date if no date string (YYYY-MM-DD) is provided.
    """
    if not date_str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        
    url = f"{BASE_URL}/category/1/scheduled-events/{date_str}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("events", [])
            return []

async def fetch_live_events():
    """Fetches currently live football matches."""
    url = f"{BASE_URL}/sport/football/events/live"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("events", [])
            return []

async def fetch_event_statistics(event_id: int):
    """Fetches detailed statistics groupings for a specific match ID."""
    url = f"{BASE_URL}/event/{event_id}/statistics"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("statistics", [])
            return []


# Maps our UI tabs to the exact string names SportAPI7 uses
TAB_MAPPINGS = {
    "key_stats": ["Total shots", "Shots on target", "Ball possession", "Total passes", "Fouls", "Yellow cards", "Red cards", "Offsides", "Corner kicks"],
    "general_play": ["Ball possession", "Total passes", "Accurate passes", "Crosses", "Throw-ins"],
    "attack": ["Total shots", "Shots on target", "Shots off target", "Blocked shots", "Corner kicks", "Offsides", "Big chances"],
    "defence": ["Tackles", "Interceptions", "Clearances", "Goalkeeper saves"],
    "discipline": ["Fouls", "Yellow cards", "Red cards"]
}

TAB_LABELS = {
    "key_stats": "Key stats",
    "general_play": "General play",
    "attack": "Attack",
    "defence": "Defence",
    "discipline": "Discipline"
}

def clean_val(val):
    """Safely converts SportAPI7 string percentages or values to numbers for comparison."""
    if val is None: return 0
    val_str = str(val).replace("%", "").strip()
    try:
        return float(val_str) if "." in val_str else int(val_str)
    except ValueError:
        return 0

def extract_flat_stats(stats_data) -> dict:
    """Flattens the nested SportAPI7 JSON groupings into a single dictionary."""
    extracted = {}
    if not stats_data: return extracted
    
    # The "ALL" period contains the full match data
    period_data = next((p for p in stats_data if p.get("period") == "ALL"), None)
    if not period_data and len(stats_data) > 0:
        period_data = stats_data[0] # Fallback to first available period
        
    if not period_data: return extracted
    
    for group in period_data.get("groups", []):
        for item in group.get("statisticsItems", []):
            extracted[item.get("name")] = {
                "home": item.get("home"),
                "away": item.get("away")
            }
            
    return extracted

def format_stats_ui(match_data: dict, stats_data: list, active_tab: str) -> str:
    """Builds the monospace layout with dynamic red/blue leading indicators."""
    home_team = match_data.get("homeTeam", {}).get("name", "Home")
    away_team = match_data.get("awayTeam", {}).get("name", "Away")
    
    home_score = match_data.get("homeScore", {}).get("current", 0)
    away_score = match_data.get("awayScore", {}).get("current", 0)
    match_status = match_data.get("status", {}).get("description", "Live")
    
    header = (
        f"**Match stats ({match_status})**\n\n"
        f"🏠 **{home_team}** `{home_score}` 🆚 `{away_score}` **{away_team}** ✈️\n\n"
    )

    flat_stats = extract_flat_stats(stats_data)
    if not flat_stats:
        return header + "*(Live statistics are not available for this match yet)*"

    rows = []
    target_stats = TAB_MAPPINGS.get(active_tab, TAB_MAPPINGS["key_stats"])

    for stat_name in target_stats:
        stat_item = flat_stats.get(stat_name, {"home": "0", "away": "0"})
        h_val = stat_item["home"]
        a_val = stat_item["away"]

        h_num = clean_val(h_val)
        a_num = clean_val(a_val)
        
        # Reverse dot logic for negative stats
        if stat_name in ["Fouls", "Yellow cards", "Red cards"]:
            h_lead = h_num > a_num 
            a_lead = a_num > h_num
        else:
            h_lead = h_num > a_num
            a_lead = a_num > h_num

        h_badge = "🔴" if h_lead else "  "
        a_badge = "🔵" if a_lead else "  "
        
        # Truncate long stat names to fit the center column
        display_label = stat_name.replace("Ball ", "").replace("Total ", "")

        rows.append(f"{h_badge} {str(h_val):>4}     {display_label:^17}     {str(a_val):<4} {a_badge}")

    table_body = "```text\n" + "\n".join(rows) + "\n```"
    return header + table_body

def build_stats_keyboard(event_id: int, active_tab: str) -> InlineKeyboardMarkup:
    """Builds the control panel exclusively with InlineKeyboardButton."""
    keyboard = []
    
    # 1. Stat Tabs
    row1, row2 = [], []
    for tab_key in ["key_stats", "general_play", "attack"]:
        label = f"🔘 {TAB_LABELS[tab_key]}" if tab_key == active_tab else TAB_LABELS[tab_key]
        row1.append(InlineKeyboardButton(label, callback_data=f"sa7_{event_id}_{tab_key}"))
        
    for tab_key in ["defence", "discipline"]:
        label = f"🔘 {TAB_LABELS[tab_key]}" if tab_key == active_tab else TAB_LABELS[tab_key]
        row2.append(InlineKeyboardButton(label, callback_data=f"sa7_{event_id}_{tab_key}"))
        
    keyboard.extend([row1, row2])
    
    # 2. System Controls
    keyboard.append([
        InlineKeyboardButton("🔄 Refresh Stats", callback_data=f"sa7_{event_id}_{active_tab}"),
        InlineKeyboardButton("📋 Back to Matches", callback_data="show_sa7_matches")
    ])
    
    return InlineKeyboardMarkup(keyboard)

# ==================== COMMAND HANDLERS ====================

# Cache to prevent making duplicate API calls when refreshing stats
MATCH_CACHE = {}

@Client.on_message(filters.command("live"))
async def cmd_live_matches(client: Client, message):
    msg = await message.reply_text("⏳ Fetching live matches from SportAPI7...")
    
    matches = await fetch_live_events()
    
    if not matches:
        return await msg.edit_text("📭 **No live matches at the moment.**")
        
    keyboard = []
    
    for m in matches[:10]: # Limit to 10 for UI scale
        event_id = m.get("id")
        MATCH_CACHE[event_id] = m  # Store basic match data for the UI formatter
        
        home = m.get("homeTeam", {}).get("name", "Home")
        away = m.get("awayTeam", {}).get("name", "Away")
        
        home_score = m.get("homeScore", {}).get("current", 0)
        away_score = m.get("awayScore", {}).get("current", 0)
        status = m.get("status", {}).get("description", "Live")
        
        btn_text = f"🟢 {home} {home_score}-{away_score} {away} ({status})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"sa7_{event_id}_key_stats")])
        
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="close_ui")])
    
    await msg.edit_text(
        "🏟 **LIVE FOOTBALL MATCHES**\nSelect a match to view in-depth statistics:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@Client.on_callback_query(filters.regex(r"^sa7_(\d+)_([a-z_]+)$"))
async def cb_update_stats(client: Client, query: CallbackQuery):
    event_id = int(query.matches[0].group(1))
    active_tab = query.matches[0].group(2)
    
    # Fetch statistics mapping
    stats_data = await fetch_event_statistics(event_id)
    match_data = MATCH_CACHE.get(event_id, {}) 
    
    if not match_data:
        return await query.answer("Match data expired. Please request the list again.", show_alert=True)
        
    text = format_stats_ui(match_data, stats_data, active_tab)
    keyboard = build_stats_keyboard(event_id, active_tab)
    
    try:
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer("Stats updated from SportAPI7!")
    except MessageNotModified:
        await query.answer("Stats are already up to date!", show_alert=False)

@Client.on_callback_query(filters.regex("^show_sa7_matches$"))
async def cb_return_to_matches(client: Client, query: CallbackQuery):
    await query.message.edit_text("⏳ Refreshing match list...")
    # Re-trigger the main command handler logic to rebuild the match selector
    await cmd_live_matches(client, query.message)

@Client.on_callback_query(filters.regex("^close_ui$"))
async def cb_close_menu(client: Client, query: CallbackQuery):
    await query.message.delete()


#====================================================

import asyncio

from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient

# RapidAPI Credentials provided in the cURL snippet
RAPID_API_KEY = "2170275bfemsh6eb2ff11d740b03p1706ebjsnff878dca22c0"
RAPID_API_HOST = "free-api-live-football-data.p.rapidapi.com"

HEADERS = {
    "x-rapidapi-key": RAPID_API_KEY,
    "x-rapidapi-host": RAPID_API_HOST,
    "Content-Type": "application/json"
}

# Supported Leagues mapped from your requirements
SUPPORTED_LEAGUES = [
    "Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Eredivisie", 
    "Primeira Liga", "Süper Lig", "Scottish Premiership", "Liga MX", "Major League Soccer", 
    "Chinese Super League", "J1 League", "K League 1", "Indian Super League", "A-League", 
    "Liga 1", "Thai League 1", "Campeonato Brasileiro Série A", "Primera División", 
    "Liga Profesional de Fútbol", "Albanian Super League", "Andorran Premier Division" # ... and all others listed
]

db_client = AsyncIOMotorClient(Comfig.MONGO_URL)
db = db_client["football_bot"]
subscriptions_col = db["chat_subscriptions"]

# ==================== API HANDLER ====================
async def fetch_upcoming_fixtures(date_str: str):
    """
    Fetches scheduled matches from the API. 
    Note: Endpoint adjusted from player-search to a schedule endpoint.
    """
    # Replace 'football-get-matches-by-date' with the exact endpoint name from the API's documentation
    url = f"https://{RAPID_API_HOST}/football-get-matches-by-date"
    params = {"date": date_str}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS, params=params) as response:
            if response.status == 200:
                return await response.json()
            return None

# ==================== UI BUILDERS ====================
def build_schedule_keyboard(chat_id: int, notifications_on: bool) -> InlineKeyboardMarkup:
    """Replicates the interactive menu from 1002474286_2.jpg."""
    notif_text = "Turn off these notifications" if notifications_on else "Turn on these notifications"
    notif_action = "notif_off" if notifications_on else "notif_on"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✔ ⭐ Follow 🇬🇧 Manchester City", callback_data="follow_mancity")],
        [InlineKeyboardButton("⭐ Follow 🇮🇹 Inter", callback_data="follow_inter")],
        [InlineKeyboardButton("Subscribe in group chat +", callback_data="sub_group")],
        [InlineKeyboardButton(notif_text, callback_data=f"toggle_{notif_action}_{chat_id}")]
    ])

def build_match_text(matches_data: dict = None) -> str:
    """Builds the text payload matching the target UI design."""
    # In production, iterate through matches_data to build this string dynamically
    return (
        "🔝 **Upcoming matches:** ([View All](https://t.me/your_bot_username?start=all))\n\n"
        "**Friendly Match**\n"
        "🔵🔵 **Manchester City - Inter** (⏰ 5:00 PM)\n"
        "🔴⚪ **Manchester United - Atletico Madrid** (⏰ 6:30 PM)"
    )

# ==================== MESSAGE HANDLERS ====================
@Client.on_message(filters.command("ffupcoming"))
async def send_scheduudle(client: Client, message: Message):
    """Sends the main schedule interface to a PM or Group."""
    chat_id = message.chat.id
    
    # Retrieve current notification settings for this specific chat
    chat_data = await subscriptions_col.find_one({"chat_id": chat_id})
    notifications_on = chat_data.get("enabled", True) if chat_data else True

    text = build_match_text()
    keyboard = build_schedule_keyboard(chat_id, notifications_on)
    
    await message.reply_text(text, reply_markup=keyboard, disable_web_page_preview=True)

# ==================== CALLBACK HANDLERS ====================
@Client.on_callback_query(filters.regex(r"^toggle_notif_(on|off)_(-?\d+)$"))
async def handle_notification_toggle(client: Client, query: CallbackQuery):
    """Handles the enable/disable scheduling option."""
    action = query.matches[0].group(1)
    chat_id = int(query.matches[0].group(2))
    
    is_enabled = True if action == "on" else False
    
    # Update MongoDB with the new preference
    await subscriptions_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": is_enabled}},
        upsert=True
    )
    
    status_msg = "enabled" if is_enabled else "disabled"
    await query.answer(f"Automated match schedules are now {status_msg}.", show_alert=True)
    
    # Refresh the UI dynamically
    try:
        await query.edit_message_reply_markup(
            reply_markup=build_schedule_keyboard(chat_id, is_enabled)
        )
    except Exception:
        pass

@Client.on_callback_query(filters.regex("^sub_group$"))
async def handle_group_subscription(client: Client, query: CallbackQuery):
    """Provides a deep link to add the bot directly to a group chat."""
    bot_info = await client.get_me()
    url = f"https://t.me/{bot_info.username}?startgroup=true"
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add Bot to Group", url=url)]])
    await query.message.edit_text(
        "To receive live match schedules in your group, click the button below to add the bot:",
        reply_markup=kb
    )

@Client.on_callback_query(filters.regex(r"^follow_(.*)$"))
async def handle_team_follow(client: Client, query: CallbackQuery):
    """Mock handler for following specific teams."""
    team_id = query.matches[0].group(1)
    await query.answer(f"You are now following {team_id}!", show_alert=False)

# ==================== BACKGROUND SCHEDULER ====================
async def match_broadcast_loop():
    """
    Runs in the background, checking the API for matches 
    and sending them to chats that have notifications enabled.
    """
    await app.start()
    print("🚀 Bot Started. Initiating broadcast loop...")
    
    while True:
        try:
            today_str = datetime.utcnow().strftime("%Y-%m-%d")
            # Fetch real data here:
            # fixtures = await fetch_upcoming_fixtures(today_str)
            
            # Find all chats where notifications are enabled
            async for chat in subscriptions_col.find({"enabled": True}):
                try:
                    # Broadcast the newly fetched schedule
                    text = build_match_text() 
                    kb = build_schedule_keyboard(chat["chat_id"], True)
                    await app.send_message(
                        chat_id=chat["chat_id"], 
                        text=text, 
                        reply_markup=kb,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"Failed to send to {chat['chat_id']}: {e}")
                    
        except Exception as e:
            print(f"Broadcast Loop Error: {e}")
            
        # Sleep for 12 hours before the next schedule push
        await asyncio.sleep(43200)
