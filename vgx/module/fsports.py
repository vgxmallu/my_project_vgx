from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
import aiohttp


from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery




client = AsyncIOMotorClient(Config.MONGO_URL)
db = client[Config.DB_NAME]

users_db = db["users"]
history_db = db["history"]


async def fetch_api(endpoint: str, params: dict = None) -> dict:
    """Asynchronous HTTP GET request to TheSportsDB"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{Config.BASE_URL}/{endpoint}", params=params) as response:
            if response.status == 200:
                return await response.json()
            return {}


async def send_team_overview(client: Client, chat_id: int, team: dict, edit_message_id: int = None):
    """Formats and sends the rich media team overview message with inline buttons."""
    team_id = team.get("idTeam")
    name = team.get("strTeam")
    league = team.get("strLeague", "Unknown League")
    stadium = team.get("strStadium", "Unknown Stadium")
    formed = team.get("intFormedYear", "N/A")
    country = team.get("strCountry", "Unknown")
    badge = team.get("strTeamBadge")
    desc = str(team.get("strDescriptionEN", ""))
    
    clean_desc = desc[:350] + "..." if len(desc) > 350 else (desc or "No description available.")
    
    text = (
        f"🛡 **{name}** (`{formed}`)\n"
        f"🌍 **Country:** {country}\n"
        f"🏆 **League:** {league}\n"
        f"🏟 **Stadium:** {stadium}\n\n"
        f"📝 **Bio:** {clean_desc}"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👕 View Roster", callback_data=f"players_{team_id}"),
            InlineKeyboardButton("📅 Upcoming", callback_data=f"next_{team_id}")
        ],
        [
            InlineKeyboardButton("🏁 Past Matches", callback_data=f"past_{team_id}")
        ]
    ])
    
    if edit_message_id:
        try:
            await client.delete_messages(chat_id, edit_message_id)
        except Exception:
            pass
        
    if badge:
        await client.send_photo(chat_id, badge, caption=text, reply_markup=keyboard)
    else:
        await client.send_message(chat_id, text, reply_markup=keyboard)

@Client.on_message(filters.command("s"))
async def starjjjssht_cmd(client: Client, message: Message):
    user = message.from_user
    
    await users_db.update_one(
        {"user_id": user.id},
        {"$set": {"first_name": user.first_name, "username": user.username}},
        upsert=True
    )
    
    text = (
        f"⚽ **Welcome to the Advanced Sports DB Bot, {user.first_name}!**\n\n"
        "I am connected to TheSportsDB and MongoDB to fetch and remember your sports data.\n\n"
        "**Available Commands:**\n"
        "🔍 `/search <team name>` - Search for any sports team\n"
        "📜 `/history` - View your recent search logs\n"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❓ Help & Info", callback_data="help_menu")]
    ])
    
    await message.reply(text, reply_markup=keyboard)

@Client.on_message(filters.command("searcht"))
async def searchfig_team_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("⚠️ **Usage:** `/search <team name>`\n*Example:* `/search Arsenal`")
    
    query = message.text.split(maxsplit=1)[1]
    
    await history_db.insert_one({"user_id": message.from_user.id, "query": query})
    
    loading_msg = await message.reply("⏳ `Searching TheSportsDB database...`")
    data = await fetch_api("searchteams.php", {"t": query})
    teams = data.get("teams")
    
    if not teams:
        return await loading_msg.edit("❌ **No teams found.**\n*(Note: The free tier key '3' is restricted to a limited database like 'Arsenal'.)*")
    
    await send_team_overview(client, message.chat.id, teams[0], loading_msg.id)


@Client.on_message(filters.command("history"))
async def history_cmd(client: Client, message: Message):
    cursor = history_db.find({"user_id": message.from_user.id}).sort("_id", -1).limit(5)
    records = await cursor.to_list(length=5)
    
    if not records:
        return await message.reply("📭 You haven't made any searches yet!")
        
    text = "📜 **Your Recent Search History:**\n\n"
    for i, r in enumerate(records, 1):
        text += f"{i}. `{r['query']}`\n"
        
    await message.reply(text)

@Client.on_callback_query(filters.regex(r"^help_menu$"))
async def help_callback(client: Client, query: CallbackQuery):
    text = "💡 **Help Menu**\n\nUse `/search <name>` to find a team. Once found, use the inline buttons to fetch live player rosters, past match scores, and upcoming schedules directly from TheSportsDB!"
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Close", callback_data="close_menu")]]))

@Client.on_callback_query(filters.regex(r"^close_menu$"))
async def close_callback(client: Client, query: CallbackQuery):
    await query.message.delete()

@Client.on_callback_query(filters.regex(r"^team_(\d+)$"))
async def team_back_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    await query.answer("Reloading team profile...")
    
    data = await fetch_api("lookupteam.php", {"id": team_id})
    if not data.get("teams"):
        return await query.answer("⚠️ Team data missing.", show_alert=True)
    
    await query.message.delete()
    await send_team_overview(client, query.message.chat.id, data["teams"][0])


@Client.on_callback_query(filters.regex(r"^players_(\d+)$"))
async def players_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    await query.answer("Fetching current roster...")
    
    team_req = await fetch_api("lookupteam.php", {"id": team_id})
    if not team_req.get("teams"):
        return await query.answer("API Error.", show_alert=True)
        
    team_name = team_req["teams"][0]["strTeam"]
    data = await fetch_api("searchplayers.php", {"t": team_name})
    players = data.get("player", [])
    
    if not players:
        return await query.message.reply("⚠️ No roster data available for this team.")
    
    text = f"👕 **{team_name} - Current Roster**\n\n"
    for p in players[:20]:
        pos = p.get("strPosition", "Unknown")
        name = p.get("strPlayer", "Unknown")
        text += f"▪️ `{pos}` - **{name}**\n"
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Team Overview", callback_data=f"team_{team_id}")]])
    await query.message.reply(text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex(r"^next_(\d+)$"))
async def next_matches_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    await query.answer("Loading upcoming fixtures...")
    
    data = await fetch_api("eventsnext.php", {"id": team_id})
    events = data.get("events")
    
    if not events:
        return await query.message.reply("📅 No upcoming fixtures scheduled.")
    
    text = "📅 **Upcoming Fixtures**\n\n"
    for e in events:
        home = e.get("strHomeTeam")
        away = e.get("strAwayTeam")
        date = e.get("dateEvent")
        time = e.get("strTime", "TBA")
        league = e.get("strLeague")
        text += f"🏆 **{league}**\n⚔️ {home} vs {away}\n🕒 `{date} • {time}`\n\n"
        
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Team Overview", callback_data=f"team_{team_id}")]])
    await query.message.reply(text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex(r"^past_(\d+)$"))
async def past_matches_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    await query.answer("Fetching recent results...")
    
    data = await fetch_api("eventslast.php", {"id": team_id})
    events = data.get("results")
    
    if not events:
        return await query.message.reply("🏁 No recent match data found.")
    
    text = "🏁 **Recent Match Results**\n\n"
    for e in events:
        home = e.get("strHomeTeam")
        away = e.get("strAwayTeam")
        h_score = e.get("intHomeScore", "?")
        a_score = e.get("intAwayScore", "?")
        date = e.get("dateEvent")
        text += f"📅 `{date}`\n⚽ {home} `{h_score} - {a_score}` {away}\n\n"
        
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Team Overview", callback_data=f"team_{team_id}")]])
    await query.message.reply(text, reply_markup=keyboard)

