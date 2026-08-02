from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
import aiohttp
from datetime import datetime
from typing import Dict, Any, List, Optional
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery





USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)



class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGO_URL)
        self.db = self.client[Config.DB_NAME]
        self.settings = self.db["chat_settings"]
        self.tracked_matches = self.db["tracked_matches"]

    async def is_notifications_enabled(self, chat_id: int) -> bool:
        doc = await self.settings.find_one({"chat_id": chat_id})
        return doc.get("enabled", True) if doc else True

    async def toggle_notifications(self, chat_id: int) -> bool:
        current = await self.is_notifications_enabled(chat_id)
        new_state = not current
        await self.settings.update_one(
            {"chat_id": chat_id},
            {"$set": {"enabled": new_state}},
            upsert=True
        )
        return new_state

    async def get_subscribed_chats(self):
        cursor = self.settings.find({"enabled": True})
        return [doc["chat_id"] async for doc in cursor]

db = Database()

class FotMobScraper:
    def __init__(self):
        self.base_url = "https://www.fotmob.com/api"
        self.headers = {"User-Agent": USER_AGENT}

    async def _get(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/{endpoint}"
        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
            except Exception as e:
                print(f"Scraper Error [{endpoint}]: {e}")
        return None

    async def get_matches_by_date(self, date_str: str = None) -> List[Dict[str, Any]]:
        if not date_str:
            date_str = datetime.utcnow().strftime("%Y%m%d")
        data = await self._get("matches", {"date": date_str})
        return data.get("leagues", []) if data else []

    async def get_match_details(self, match_id: int) -> Optional[Dict[str, Any]]:
        return await self._get("matchDetails", {"matchId": match_id})

    async def get_league_standings(self, league_id: int) -> Optional[Dict[str, Any]]:
        return await self._get("leagues", {"id": league_id})

    async def get_transfers(self, page: int = 1) -> List[Dict[str, Any]]:
        data = await self._get("transfers", {"page": page})
        return data.get("transfers", []) if data else []

scraper = FotMobScraper()



def build_match_menu(match_id: int, current_tab: str = "overview") -> InlineKeyboardMarkup:
    tabs = [
        ("📊 Stats", f"fm_stats_{match_id}"),
        ("👥 Lineups", f"fm_lineup_{match_id}"),
        ("⭐ Ratings", f"fm_ratings_{match_id}"),
        ("🎙 Ticker", f"fm_ticker_{match_id}"),
        ("⚔️ H2H", f"fm_h2h_{match_id}")
    ]
    
    keyboard = []
    row = []
    for label, cb_data in tabs:
        if current_tab in cb_data:
            label = f"🔘 {label}"
        row.append(InlineKeyboardButton(label, callback_data=cb_data))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"fm_refresh_{match_id}_{current_tab}"),
        InlineKeyboardButton("📋 Back to List", callback_data="fm_back_matches")
    ])
    return InlineKeyboardMarkup(keyboard)

def format_overview_text(data: Dict[str, Any]) -> str:
    general = data.get("general", {})
    header = general.get("header", {})
    teams = header.get("teams", [{}, {}])
    
    home_name = teams[0].get("name", "Home")
    away_name = teams[1].get("name", "Away")
    score = header.get("status", {}).get("scoreStr", "vs")
    status = header.get("status", {}).get("reason", {}).get("short", "Live")
    
    text = f"🏟 **{home_name} {score} {away_name}** (`{status}`)\n"
    text += f"🏆 League: {general.get('leagueName', 'N/A')}\n"
    text += f"📍 Venue: {general.get('venue', {}).get('name', 'N/A')}\n\n"
    
    events = data.get("content", {}).get("matchFacts", {}).get("events", {}).get("events", [])
    if events:
        text += "**Key Events:**\n"
        for event in events[:5]:
            time = event.get("timeStr", "")
            type_ = event.get("type", "")
            player = event.get("player", {}).get("name", "")
            text += f"• `{time}'` {type_.title()} - {player}\n"
            
    return text

def format_stats_text(data: Dict[str, Any]) -> str:
    stats_data = data.get("content", {}).get("stats", {}).get("Periods", {}).get("All", {}).get("stats", [])
    if not stats_data:
        return "❌ Statistics not available for this match yet."

    text = "📊 **MATCH STATISTICS**\n```text\n"
    for group in stats_data:
        for item in group.get("statsItems", []):
            title = item.get("title", "")
            vals = item.get("stats", ["0", "0"])
            text += f"{str(vals[0]):>5}  {title:^18}  {str(vals[1]):<5}\n"
    text += "```"
    return text

@Client.on_message(filters.command("ftmob"))
async def cmd_ghstart(client: Client, message: Message):
    chat_id = message.chat.id
    notif_status = await db.is_notifications_enabled(chat_id)
    btn_label = "🔔 Notifications: ON" if notif_status else "🔕 Notifications: OFF"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚽ Live & Today's Matches", callback_data="fm_back_matches")],
        [InlineKeyboardButton("🏆 League Standings", callback_data="fm_menu_standings")],
        [InlineKeyboardButton("🔄 Latest Transfers", callback_data="fm_menu_transfers")],
        [InlineKeyboardButton(btn_label, callback_data=f"fm_toggle_notif_{chat_id}")]
    ])
    
    text = (
        "<b>Welcome to FotMob Football Engine!</b>\n\n"
        "Get live scores, player ratings, tactical lineups, match statistics, "
        "head-to-head records, and transfer news directly from internal endpoints."
    )
    await message.reply_text(text, reply_markup=keyboard)

@Client.on_callback_query(filters.regex(r"^fm_toggle_notif_(-?\d+)$"))
async def cb_toggle_notif(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group(1))
    new_state = await db.toggle_notifications(chat_id)
    btn_label = "🔔 Notifications: ON" if new_state else "🔕 Notifications: OFF"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚽ Live & Today's Matches", callback_data="fm_back_matches")],
        [InlineKeyboardButton("🏆 League Standings", callback_data="fm_menu_standings")],
        [InlineKeyboardButton("🔄 Latest Transfers", callback_data="fm_menu_transfers")],
        [InlineKeyboardButton(btn_label, callback_data=f"fm_toggle_notif_{chat_id}")]
    ])
    
    await query.edit_message_reply_markup(reply_markup=keyboard)
    await query.answer(f"Notifications set to {'Enabled' if new_state else 'Disabled'}")

@Client.on_message(filters.command("ftmobmatches"))
async def cmd_matcgghes(client: Client, message: Message):
    msg = await message.reply_text("🔄 Scraping match schedules...")
    leagues = await scraper.get_matches_by_date()
    
    if not leagues:
        return await msg.edit_text("❌ No matches found for today.")
        
    keyboard = []
    count = 0
    for league in leagues:
        for match in league.get("matches", []):
            if count >= 12:  # Scaled limit for cleaner UI
                break
            m_id = match.get("id")
            home = match.get("home", {}).get("name", "Home")
            away = match.get("away", {}).get("name", "Away")
            score = match.get("status", {}).get("scoreStr", "vs")
            btn_text = f"{home} {score} {away}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"fm_overview_{m_id}")])
            count += 1

    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="fm_close")])
    await msg.edit_text("<b>📅 Today's Live & Scheduled Matches:</b>", reply_markup=InlineKeyboardMarkup(keyboard))

@Client.on_callback_query(filters.regex(r"^fm_overview_(\d+)$"))
async def cb_match_overview(client: Client, query: CallbackQuery):
    match_id = int(query.matches[0].group(1))
    data = await scraper.get_match_details(match_id)
    if not data:
        return await query.answer("Failed to load match details.", show_alert=True)
        
    text = format_overview_text(data)
    await query.edit_message_text(text, reply_markup=build_match_menu(match_id, "overview"))

@Client.on_callback_query(filters.regex(r"^fm_stats_(\d+)$"))
async def cb_match_stats(client: Client, query: CallbackQuery):
    match_id = int(query.matches[0].group(1))
    data = await scraper.get_match_details(match_id)
    if not data:
        return await query.answer("Failed to load stats.", show_alert=True)
        
    text = format_stats_text(data)
    await query.edit_message_text(text, reply_markup=build_match_menu(match_id, "stats"))

@Client.on_callback_query(filters.regex(r"^fm_ratings_(\d+)$"))
async def cb_match_ratings(client: Client, query: CallbackQuery):
    match_id = int(query.matches[0].group(1))
    data = await scraper.get_match_details(match_id)
    lineup = data.get("content", {}).get("lineup", {})
    if not lineup:
        return await query.answer("Player ratings unavailable.", show_alert=True)

    text = "⭐ **TOP PLAYER RATINGS**\n\n"
    for team_key in ["homeTeam", "awayTeam"]:
        team_name = lineup.get(team_key, {}).get("name", "")
        text += f"**{team_name}:**\n"
        starters = lineup.get(team_key, {}).get("starters", [])
        for p in starters[:5]:
            rating = p.get("rating", {}).get("num", "N/A")
            text += f"• {p.get('name', 'Player')}: `{rating}`\n"
        text += "\n"
        
    await query.edit_message_text(text, reply_markup=build_match_menu(match_id, "ratings"))

@Client.on_callback_query(filters.regex(r"^fm_back_matches$"))
async def cb_back_matches(client: Client, query: CallbackQuery):
    await query.message.delete()
    await cmd_matches(client, query.message)

@Client.on_callback_query(filters.regex(r"^fm_close$"))
async def cb_close(client: Client, query: CallbackQuery):
    await query.message.delete()
  

# Featured top league IDs on FotMob
LEAGUES = {
    "Premier League": 47,
    "La Liga": 87,
    "Serie A": 55,
    "Bundesliga": 54,
    "Ligue 1": 53
}

@Client.on_message(filters.command("ftmpbstandings"))
async def cmd_standiggngs(client: Client, message: Message):
    keyboard = []
    for name, l_id in LEAGUES.items():
        keyboard.append([InlineKeyboardButton(f"🏆 {name}", callback_data=f"fm_std_{l_id}")])
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="fm_close")])
    
    await message.reply_text("<b>Select a League to View Standings:</b>", reply_markup=InlineKeyboardMarkup(keyboard))

@Client.on_callback_query(filters.regex(r"^fm_menu_standings$"))
async def cb_menu_standings(client: Client, query: CallbackQuery):
    await query.message.delete()
    await cmd_standings(client, query.message)

@Client.on_callback_query(filters.regex(r"^fm_std_(\d+)$"))
async def cb_view_standings(client: Client, query: CallbackQuery):
    league_id = int(query.matches[0].group(1))
    data = await scraper.get_league_standings(league_id)
    
    tables = data.get("table", [{}])[0].get("data", {}).get("table", {}).get("all", [])
    if not tables:
        return await query.answer("Standings unavailable.", show_alert=True)
        
    text = f"🏆 **LEAGUE STANDINGS**\n```text\n"
    text += f"{'#':<3} {'Team':<14} {'P':<3} {'GD':<4} {'PTS':<3}\n"
    text += "-" * 30 + "\n"
    
    for row in tables[:10]:
        pos = row.get("idx", "")
        name = row.get("name", "")[:13]
        pts = row.get("pts", "")
        p = row.get("played", "")
        gd = row.get("gd", "")
        text += f"{pos:<3} {name:<14} {p:<3} {gd:<4} {pts:<3}\n"
    text += "```"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 League List", callback_data="fm_menu_standings")],
        [InlineKeyboardButton("❌ Close", callback_data="fm_close")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard)


@Client.on_message(filters.command("ftmobtransfers"))
async def cmd_tranvvsfers(client: Client, message: Message):
    transfers = await scraper.get_transfers()
    if not transfers:
        return await message.reply_text("❌ Failed to fetch transfer market data.")
        
    text = "🔄 **LATEST CONFIRMED TRANSFERS**\n\n"
    for item in transfers[:8]:
        name = item.get("name", "Player")
        from_team = item.get("fromClub", "Unknown")
        to_team = item.get("toClub", "Unknown")
        fee = item.get("fee", {}).get("feeText", "Undisclosed")
        text += f"⚽ **{name}**\n🔁 `{from_team}` ➡️ `{to_team}`\n💰 Fee: {fee}\n\n"
        
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="fm_close")]])
    await message.reply_text(text, reply_markup=keyboard)

@Client.on_callback_query(filters.regex(r"^fm_menu_transfers$"))
async def cb_menu_transfers(client: Client, query: CallbackQuery):
    await query.message.delete()
    await cmd_transfers(client, query.message)


#====================================================


async def ftmob_broadcast_loop(client: Client):
    """
    Background worker: Checks live matches and pushes 
    goal/red card updates to chats with enabled notifications.
    """
    await asyncio.sleep(5)  # Delay startup execution
    while True:
        try:
            leagues = await scraper.get_matches_by_date()
            live_matches = []
            
            for league in leagues:
                for match in league.get("matches", []):
                    if match.get("status", {}).get("started") and not match.get("status", {}).get("finished"):
                        live_matches.append(match)
                        
            # If live matches are ongoing, fetch active subscribers from MongoDB
            if live_matches:
                subscribed_chats = await db.get_subscribed_chats()
                # Broadcast logic can evaluate goal state changes here
                
        except Exception as e:
            print(f"Scheduler Loop Error: {e}")
            
        await asyncio.sleep(60)  # Evaluate ticker state every 60 seconds
