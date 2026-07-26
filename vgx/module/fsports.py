from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
import aiohttp
import random

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import asyncio
from datetime import datetime
from pyrogram.errors import FloodWait



client = AsyncIOMotorClient(Config.MONGO_URL)
db = client[Config.DB_NAME]

users_db = db["users"]
history_db = db["history"]
favorites_db = db["favorites"]
predictions_db = db["predictions"]
points_db = db["points"]

settings_col = db["broadcast_settings"]

# Active background task tracking dictionary: { chat_id: asyncio.Task }
active_schedulers = {}

async def get_settings(chat_id: int):
    doc = await settings_col.find_one({"chat_id": chat_id})
    if not doc:
        # Default settings: Disabled, 1 hour interval, 300s delete, pin disabled
        doc = {
            "chat_id": chat_id,
            "enabled": False,
            "interval_seconds": 3600,  # 1 hour
            "interval_label": "1h",
            "delete_seconds": 300,     # 300s (5 mins)
            "delete_label": "300s",
            "pin_enabled": False
        }
        await settings_col.update_one({"chat_id": chat_id}, {"$set": doc}, upsert=True)
    return doc

# --- Background Broadcaster Loop ---
async def broadcast_loop(client: Client, chat_id: int):
    while True:
        try:
            config = await get_settings(chat_id)
            if not config.get("enabled", False):
                break
            
            interval = config.get("interval_seconds", 3600)
            del_time = config.get("delete_seconds", 300)
            pin_on = config.get("pin_enabled", False)
            
            # Fetch live/today matches from sports API (using eventsday endpoint or fallback search)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            from services.sports_api import fetch_api
            api_data = await fetch_api("eventsday.php", {"d": today})
            events = api_data.get("events", [])
            
            text = f"⚽ **Live & Upcoming Match Schedule Updates** ({today})\n\n"
            if not events:
                text += "No live or scheduled fixtures recorded for today yet. Check back soon!"
            else:
                for e in events[:5]:
                    status = e.get('strStatus', 'NS')
                    score = f"{e.get('intHomeScore', '0')} - {e.get('intAwayScore', '0')}" if status != 'NS' else "vs"
                    text += (
                        f"🏆 **{e.get('strLeague', 'League')}**\n"
                        f"⚔️ {e.get('strHomeTeam')} `{score}` {e.get('strAwayTeam')}\n"
                        f"🕒 Status: `{status} | {e.get('strTime', 'TBA')}`\n\n"
                    )
            
            # Send message
            msg = await client.send_message(chat_id, text, parse_mode=None)
            
            # Handle Pinning
            if pin_on:
                try:
                    await msg.pin(disable_notification=True)
                except Exception:
                    pass
            
            # Handle Auto-Deletion Task
            if del_time > 0:
                async def delete_later():
                    await asyncio.sleep(del_time)
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                asyncio.create_task(delete_later())
                
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Broadcast loop error in chat {chat_id}: {e}")
            await asyncio.sleep(60)

def restart_scheduler_task(client: Client, chat_id: int, enabled: bool):
    if chat_id in active_schedulers:
        active_schedulers[chat_id].cancel()
        del active_schedulers[chat_id]
    if enabled:
        active_schedulers[chat_id] = asyncio.create_task(broadcast_loop(client, chat_id))


# --- Command & Panel Interface ---
@Client.on_message(filters.command("liveschedule") & filters.group)
async def liveschedule_group_cmd(client: Client, message: Message):
    chat_id = message.chat.id
    config = await get_settings(chat_id)
    
    status_text = "🟢 **ENABLED**" if config["enabled"] else "🔴 **DISABLED**"
    pin_text = "✅ Enabled" if config["pin_enabled"] else "❌ Disabled"
    
    text = (
        f"⚙️ **Live Schedule Broadcast Control Panel**\n\n"
        f"• **Status:** {status_text}\n"
        f"• **Interval:** `{config.get('interval_label', '1h')}`\n"
        f"• **Auto-Delete:** `{config.get('delete_label', '300s')}`\n"
        f"• **Pin Message:** {pin_text}\n\n"
        f"Use the buttons below to customize settings:"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Toggle: {'🟢 ON' if config['enabled'] else '🔴 OFF'}", callback_data=f"ls_toggle_{chat_id}")],
        [
            InlineKeyboardButton("⏱ 1m", callback_data=f"ls_int_{chat_id}_60_1m"),
            InlineKeyboardButton("⏱ 5m", callback_data=f"ls_int_{chat_id}_300_5m"),
            InlineKeyboardButton("⏱ 20m", callback_data=f"ls_int_{chat_id}_1200_20m"),
        ],
        [
            InlineKeyboardButton("⏱ 30m", callback_data=f"ls_int_{chat_id}_1800_30m"),
            InlineKeyboardButton("⏱ 1h", callback_data=f"ls_int_{chat_id}_3600_1h"),
            InlineKeyboardButton("⏱ 2h+", callback_data=f"ls_int_{chat_id}_7200_2h"),
        ],
        [
            InlineKeyboardButton("🗑 Del: 30s", callback_data=f"ls_del_{chat_id}_30_30s"),
            InlineKeyboardButton("🗑 Del: 300s", callback_data=f"ls_del_{chat_id}_300_300s"),
            InlineKeyboardButton("🗑 Del: 400s", callback_data=f"ls_del_{chat_id}_400_400s"),
            InlineKeyboardButton("🗑 Del: 2400s", callback_data=f"ls_del_{chat_id}_2400_2400s"),
        ],
        [InlineKeyboardButton(f"📌 Pin Mode: {pin_text}", callback_data=f"ls_pin_{chat_id}")]
    ])
    
    await message.reply(text, reply_markup=keyboard, parse_mode=None)


# --- Private Target Group Management Command ---
@Client.on_message(filters.command("targetschedule") & filters.private)
async def target_schedule_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("⚠️ Usage: `/targetschedule <group_id>`\n*(Example: `/targetschedule -1001234567890`)*", parse_mode=None)
    
    try:
        target_chat_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid Group ID format. Must be an integer (e.g., `-100...`).", parse_mode=None)
    
    config = await get_settings(target_chat_id)
    status_text = "🟢 **ENABLED**" if config["enabled"] else "🔴 **DISABLED**"
    
    text = (
        f"🎯 **Target Group Control Panel**\n"
        f"Target ID: `{target_chat_id}`\n\n"
        f"• **Status:** {status_text}\n"
        f"• **Interval:** `{config.get('interval_label', '1h')}`\n"
        f"• **Auto-Delete:** `{config.get('delete_label', '300s')}`\n"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Toggle Module: {'🟢 ON' if config['enabled'] else '🔴 OFF'}", callback_data=f"ls_toggle_{target_chat_id}")],
        [InlineKeyboardButton("🔄 Refresh Panel", callback_data=f"ls_refresh_{target_chat_id}")]
    ])
    
    await message.reply(text, reply_markup=keyboard, parse_mode=None)


# --- Callback Handlers for Control Settings ---
@Client.on_callback_query(filters.regex(r"^ls_toggle_(-?\d+)$"))
async def ls_toggle_callback(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group(1))
    config = await get_settings(chat_id)
    
    new_status = not config["enabled"]
    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"enabled": new_status}}, upsert=True)
    restart_scheduler_task(client, chat_id, new_status)
    
    await query.answer(f"Module successfully {'Enabled'ekyll}!" if new_status else "Module Disabled.", show_alert=True)
    
    # Refresh view
    updated_config = await get_settings(chat_id)
    status_text = "🟢 **ENABLED**" if updated_config["enabled"] else "🔴 **DISABLED**"
    pin_text = "✅ Enabled" if updated_config["pin_enabled"] else "❌ Disabled"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Toggle: {'🟢 ON' if updated_config['enabled'] else '🔴 OFF'}", callback_data=f"ls_toggle_{chat_id}")],
        [
            InlineKeyboardButton("⏱ 1m", callback_data=f"ls_int_{chat_id}_60_1m"),
            InlineKeyboardButton("⏱ 5m", callback_data=f"ls_int_{chat_id}_300_5m"),
            InlineKeyboardButton("⏱ 20m", callback_data=f"ls_int_{chat_id}_1200_20m"),
        ],
        [
            InlineKeyboardButton("⏱ 30m", callback_data=f"ls_int_{chat_id}_1800_30m"),
            InlineKeyboardButton("⏱ 1h", callback_data=f"ls_int_{chat_id}_3600_1h"),
            InlineKeyboardButton("⏱ 2h+", callback_data=f"ls_int_{chat_id}_7200_2h"),
        ],
        [
            InlineKeyboardButton("🗑 Del: 30s", callback_data=f"ls_del_{chat_id}_30_30s"),
            InlineKeyboardButton("🗑 Del: 300s", callback_data=f"ls_del_{chat_id}_300_300s"),
            InlineKeyboardButton("🗑 Del: 400s", callback_data=f"ls_del_{chat_id}_400_400s"),
            InlineKeyboardButton("🗑 Del: 2400s", callback_data=f"ls_del_{chat_id}_2400_2400s"),
        ],
        [InlineKeyboardButton(f"📌 Pin Mode: {pin_text}", callback_data=f"ls_pin_{chat_id}")]
    ])
    
    await query.message.edit_text(
        f"⚙️ **Live Schedule Broadcast Control Panel** (Chat: `{chat_id}`)\n\n"
        f"• **Status:** {status_text}\n"
        f"• **Interval:** `{updated_config.get('interval_label', '1h')}`\n"
        f"• **Auto-Delete:** `{updated_config.get('delete_label', '300s')}`\n"
        f"• **Pin Message:** {pin_text}",
        reply_markup=keyboard,
        parse_mode=None
    )

@Client.on_callback_query(filters.regex(r"^ls_int_(-?\d+)_(\d+)_([a-zA-Z0-9\+]+)$"))
async def ls_interval_callback(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group(1))
    seconds = int(query.matches[0].group(2))
    label = query.matches[0].group(3)
    
    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"interval_seconds": seconds, "interval_label": label}}, upsert=True)
    
    # Restart task loop with new timer if enabled
    config = await get_settings(chat_id)
    if config["enabled"]:
        restart_scheduler_task(client, chat_id, True)
        
    await query.answer(f"Interval updated to {label}!", show_alert=True)


@Client.on_callback_query(filters.regex(r"^ls_del_(-?\d+)_(\d+)_([a-zA-Z0-9]+)$"))
async def ls_delete_callback(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group(1))
    seconds = int(query.matches[0].group(2))
    label = query.matches[0].group(3)
    
    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"delete_seconds": seconds, "delete_label": label}}, upsert=True)
    await query.answer(f"Auto-delete timer set to {label}!", show_alert=True)


@Client.on_callback_query(filters.regex(r"^ls_pin_(-?\d+)$"))
async def ls_pin_callback(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group(1))
    config = await get_settings(chat_id)
    
    new_pin = not config["pin_enabled"]
    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"pin_enabled": new_pin}}, upsert=True)
    await query.answer(f"Pin feature {'Enabled' if new_pin else 'Disabled'}!", show_alert=True)

async def fetch_api(endpoint: str, params: dict = None) -> dict:
    """Asynchronous HTTP GET request to TheSportsDB"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{Config.BASE_URL}/{endpoint}", params=params) as response:
            if response.status == 200:
                return await response.json()
            return {}

async def send_team_overview(client: Client, chat_id: int, team: dict, is_favorite: bool = False, edit_message_id: int = None):
    team_id = team.get("idTeam")
    name = team.get("strTeam")
    league = team.get("strLeague", "Unknown League")
    stadium = team.get("strStadium", "Unknown Stadium")
    formed = team.get("intFormedYear", "N/A")
    country = team.get("strCountry", "Unknown")
    badge = team.get("strTeamBadge")
    desc = str(team.get("strDescriptionEN", ""))
    
    clean_desc = desc[:300] + "..." if len(desc) > 300 else (desc or "No description available.")
    
    text = (
        f"🛡 **{name}** (`{formed}`)\n"
        f"🌍 **Country:** {country}\n"
        f"🏆 **League:** {league}\n"
        f"🏟 **Stadium:** {stadium}\n\n"
        f"📝 **Bio:** {clean_desc}"
    )
    
    fav_text = "❌ Unsave" if is_favorite else "⭐ Save Favorite"
    fav_callback = f"fav_rem_{team_id}" if is_favorite else f"fav_add_{team_id}"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👕 Roster", callback_data=f"players_{team_id}"),
            InlineKeyboardButton("📅 Schedule", callback_data=f"next_{team_id}")
        ],
        [
            InlineKeyboardButton("🏁 Results", callback_data=f"past_{team_id}"),
            InlineKeyboardButton("📺 TV Guide", callback_data=f"tv_{team_id}")
        ],
        [
            InlineKeyboardButton("🏟 Stadium & Weather", callback_data=f"stadium_{team_id}"),
            InlineKeyboardButton("🎥 Highlights", callback_data=f"high_{team_id}")
        ],
        [
            InlineKeyboardButton(fav_text, callback_data=fav_callback)
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



@Client.on_message(filters.command("cdm"))
async def startfff_cmd(client: Client, message: Message):
    user = message.from_user
    await users_db.update_one({"user_id": user.id}, {"$set": {"first_name": user.first_name}}, upsert=True)
    
    text = (
        f"⚽ **Welcome to Ultimate SportsBot, {user.first_name}!**\n\n"
        "**Core Commands:**\n"
        "🔍 /search <team> - Team profile & tools\n"
        "👤 /player <name> - Player biography\n"
        "🏆 /standings <id> - League table\n"
        "⚔️ /h2h <team1_id> <team2_id> - Compare teams\n"
        "⚽ /predict <home> vs <away> <score> - Predict match\n"
        "📊 /leaderboard - Predictor leaderboard\n"
        "🧠 /trivia - Daily football trivia quiz\n"
        "📰 /news - Latest transfer & club news\n"
    )
    await message.reply(text, parse_mode=None)


@Client.on_message(filters.command("search"))
async def search_team_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("⚠️ Usage: /search <team name>", parse_mode=None)
    
    query = message.text.split(maxsplit=1)[1]
    loading = await message.reply("⏳ Searching database...", parse_mode=None)
    data = await fetch_api("searchteams.php", {"t": query})
    teams = data.get("teams")
    
    if not teams:
        return await loading.edit("❌ No teams found.", parse_mode=None)
    
    team = teams[0]
    is_fav = await favorites_db.find_one({"user_id": message.from_user.id, "team_id": team.get("idTeam")}) is not None
    await send_team_overview(client, message.chat.id, team, is_favorite=is_fav, edit_message_id=loading.id)


@Client.on_message(filters.command("player"))
async def player_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("⚠️ Usage: /player <player name>", parse_mode=None)
    
    query = message.text.split(maxsplit=1)[1]
    loading = await message.reply("⏳ Searching player bio...", parse_mode=None)
    data = await fetch_api("searchplayers.php", {"p": query})
    players = data.get("player")
    
    await loading.delete()
    if not players:
        return await message.reply("❌ No player found with that name.", parse_mode=None)
        
    p = players[0]
    text = (
        f"👤 **{p.get('strPlayer')}**\n"
        f"🛡 **Team:** {p.get('strTeam', 'N/A')}\n"
        f"⚽ **Position:** {p.get('strPosition', 'N/A')}\n"
        f"📅 **Born:** {p.get('dateBorn', 'N/A')}\n"
        f"🌍 **Nationality:** {p.get('strNationality', 'N/A')}\n\n"
        f"📝 {str(p.get('strDescriptionEN', 'No biography available.'))[:300]}"
    )
    thumb = p.get('strThumb')
    if thumb:
        await message.reply_photo(thumb, caption=text)
    else:
        await message.reply(text, parse_mode=None)


@Client.on_message(filters.command("h2h"))
async def h2h_cmd(client: Client, message: Message):
    if len(message.command) < 3:
        return await message.reply("⚠️ Usage: /h2h <team1_id> <team2_id>\n(Example: /h2h 133602 133604)", parse_mode=None)
    
    t1_id, t2_id = message.command[1], message.command[2]
    t1_data = await fetch_api("lookupteam.php", {"id": t1_id})
    t2_data = await fetch_api("lookupteam.php", {"id": t2_id})
    
    if not t1_data.get("teams") or not t2_data.get("teams"):
        return await message.reply("❌ Invalid Team IDs provided.", parse_mode=None)
        
    t1 = t1_data["teams"][0]
    t2 = t2_data["teams"][0]
    
    text = (
        f"⚔️ **Head-to-Head Analytics Comparison**\n\n"
        f"🛡 **{t1['strTeam']}** vs **{t2['strTeam']}**\n\n"
        f"🌍 **Countries:** {t1['strCountry']} vs {t2['strCountry']}\n"
        f"🏆 **Leagues:** {t1['strLeague']} | {t2['strLeague']}\n"
        f"🏟 **Stadiums:** {t1['strStadium']} vs {t2['strStadium']}\n"
        f"📅 **Formed:** {t1['intFormedYear']} vs {t2['intFormedYear']}"
    )
    await message.reply(text)


@Client.on_message(filters.command("predict"))
async def predict_cmd(client: Client, message: Message):
    if len(message.command) < 4:
        return await message.reply("⚠️ Usage: /predict Arsenal vs Chelsea 2-1", parse_mode=None)
    
    match_str = f"{message.command[1]} {message.command[2]} {message.command[3]}"
    score = message.command[4] if len(message.command) > 4 else "1-1"
    
    await predictions_db.insert_one({
        "user_id": message.from_user.id,
        "name": message.from_user.first_name,
        "match": match_str,
        "score": score
    })
    await message.reply(f"✅ Prediction recorded for **{match_str}** with score **{score}**!")


@Client.on_message(filters.command("leaderboard"))
async def leaderboard_cmd(client: Client, message: Message):
    cursor = points_db.find().sort("points", -1).limit(10)
    top_users = await cursor.to_list(length=10)
    
    text = "📊 **Predictor League Leaderboard**\n\n"
    if not top_users:
        text += "No active predictor scores recorded yet. Make a prediction using /predict!"
    else:
        for i, u in enumerate(top_users, 1):
            text += f"{i}. **{u.get('name')}** - {u.get('points', 0)} pts\n"
            
    await message.reply(text)


@Client.on_message(filters.command("trivia"))
async def trivia_cmd(client: Client, message: Message):
    questions = [
        {"q": "Which club won the UEFA Champions League in 2023?", "options": ["Real Madrid", "Manchester City", "Inter Milan", "Bayern Munich"], "correct": 1},
        {"q": "Who holds the record for most goals in a single Premier League season?", "options": ["Thierry Henry", "Cristiano Ronaldo", "Erling Haaland", "Harry Kane"], "correct": 2},
        {"q": "Which country won the 2022 FIFA World Cup?", "options": ["France", "Brazil", "Argentina", "Germany"], "correct": 2},
        {"q": "Who has won the most Ballon d'Or awards in football history?", "options": ["Cristiano Ronaldo", "Lionel Messi", "Michel Platini", "Johan Cruyff"], "correct": 1},
        {"q": "Which national team won UEFA Euro 2024?", "options": ["England", "France", "Spain", "Germany"], "correct": 2},
        {"q": "Who is the all-time top goalscorer in the UEFA Champions League?", "options": ["Lionel Messi", "Robert Lewandowski", "Karim Benzema", "Cristiano Ronaldo"], "correct": 3},
        {"q": "Which national team holds the record for the most FIFA World Cup titles?", "options": ["Germany", "Italy", "Brazil", "Argentina"], "correct": 2},
        {"q": "Which manager won the historic treble with Manchester City in the 2022-23 season?", "options": ["Jurgen Klopp", "Pep Guardiola", "Mikel Arteta", "Carlo Ancelotti"], "correct": 1},
        {"q": "Which Italian club is famously nicknamed 'The Old Lady' (La Vecchia Signora)?", "options": ["AC Milan", "Inter Milan", "AS Roma", "Juventus"], "correct": 3},
        {"q": "Who scored the infamous 'Hand of God' goal during the 1986 FIFA World Cup?", "options": ["Pelé", "Diego Maradona", "Zinedine Zidane", "Ronaldo Nazário"], "correct": 1},
        {"q": "Which Premier League club plays its home matches at Anfield?", "options": ["Everton", "Manchester United", "Liverpool", "Arsenal"], "correct": 2},
        {"q": "Who won the Golden Boot award at the 2022 FIFA World Cup?", "options": ["Lionel Messi", "Kylian Mbappé", "Olivier Giroud", "Julián Álvarez"], "correct": 1},
        {"q": "Which player scored the fastest goal in World Cup history (in 11 seconds)?", "options": ["Hakan Şükür", "Clas Rydell", "Václav Mašek", "Bryan Robson"], "correct": 0},
        {"q": "Which country hosted the 2014 FIFA World Cup?", "options": ["South Africa", "Brazil", "Germany", "Russia"], "correct": 1},
        {"q": "Who holds the record for the most clean sheets in Premier League history?", "options": ["David de Gea", "Peter Schmeichel", "Petr Čech", "Edwin van der Sar"], "correct": 2},
        {"q": "Which club won the very first European Cup (now UEFA Champions League) in 1955-56?", "options": ["AC Milan", "Real Madrid", "Benfica", "Reims"], "correct": 1},
        {"q": "Who is the all-time top goalscorer for the Brazil men's national team?", "options": ["Pelé", "Ronaldo", "Neymar", "Romário"], "correct": 2},
        {"q": "Which stadium is famously known as the 'Theatre of Dreams'?", "options": ["Anfield", "Wembley Stadium", "Old Trafford", "Camp Nou"], "correct": 2},
        {"q": "Which player won the 2018 Ballon d'Or, breaking the decade-long Messi-Ronaldo monopoly?", "options": ["Antoine Griezmann", "Luka Modrić", "Kylian Mbappé", "Neymar"], "correct": 1},
        {"q": "Who is the all-time leading goalscorer in international men's football history?", "options": ["Ali Daei", "Lionel Messi", "Cristiano Ronaldo", "Sunil Chhetri"], "correct": 2},
        {"q": "Which club won the English Premier League 'Invincibles' season without losing a single match?", "options": ["Manchester United", "Chelsea", "Arsenal", "Liverpool"], "correct": 2},
        {"q": "Which manager holds the record for the most UEFA Champions League titles won?", "options": ["Pep Guardiola", "Sir Alex Ferguson", "Zinedine Zidane", "Carlo Ancelotti"], "correct": 3},
        {"q": "Who scored the winning extra-time goal for Germany in the 2014 World Cup Final?", "options": ["Miroslav Klose", "Mario Götze", "Thomas Müller", "Toni Kroos"], "correct": 1},
        {"q": "Which African nation made history by reaching the semi-finals of the 2022 FIFA World Cup?", "options": ["Senegal", "Cameroon", "Ghana", "Morocco"], "correct": 3},
        {"q": "Who remains the youngest player to score a goal in a FIFA World Cup tournament?", "options": ["Michael Owen", "Lionel Messi", "Pelé", "Gavi"], "correct": 2},
        {"q": "Which Spanish club plays its home matches at the Metropolitano Stadium?", "options": ["Real Madrid", "Atlético Madrid", "Valencia CF", "Sevilla FC"], "correct": 1},
        {"q": "Which goalkeeper famously performed the 'scorpion kick' save against England in 1995?", "options": ["Manuel Neuer", "René Higuita", "Jorge Campos", "Peter Schmeichel"], "correct": 1},
        {"q": "Which country won the UEFA Euro 2020 tournament (held in 2021)?", "options": ["England", "Italy", "Denmark", "Spain"], "correct": 1},
        {"q": "Who holds the all-time record for the most assists in Premier League history?", "options": ["Frank Lampard", "Kevin De Bruyne", "Ryan Giggs", "Cesc Fàbregas"], "correct": 2},
        {"q": "Which club did David Beckham join after leaving Real Madrid in 2007?", "options": ["AC Milan", "LA Galaxy", "Paris Saint-Germain", "Manchester United"], "correct": 1},
        {"q": "Which country won the 1998 FIFA World Cup which they hosted?", "options": ["Brazil", "France", "Italy", "Argentina"], "correct": 1},
        {"q": "Which player won the 2009 FIFA Puskás Award for a stunning long-range strike against Porto?", "options": ["Cristiano Ronaldo", "Lionel Messi", "Grafite", "Andrés Iniesta"], "correct": 0},
        {"q": "Which country hosted the 2010 FIFA World Cup, the first time it was held in Africa?", "options": ["Egypt", "Morocco", "South Africa", "Nigeria"], "correct": 2},
        {"q": "Who is the all-time top goalscorer in Serie A history?", "options": ["Francesco Totti", "Silvio Piola", "Giuseppe Meazza", "Ciro Immobile"], "correct": 1},
        {"q": "Which German powerhouse club is nicknamed 'Die Roten' (The Reds)?", "options": ["Borussia Dortmund", "RB Leipzig", "Bayern Munich", "Bayer Leverkusen"], "correct": 2},
        {"q": "Which player scored five goals in just nine minutes against VfL Wolfsburg in 2015?", "options": ["Thomas Müller", "Robert Lewandowski", "Erling Haaland", "Pierre-Emerick Aubameyang"], "correct": 1},
        {"q": "Which country won the inaugural FIFA World Cup tournament in 1930?", "options": ["Argentina", "Uruguay", "Brazil", "Italy"], "correct": 1},
        {"q": "Which English club won the Champions League in 2012 under manager Roberto Di Matteo?", "options": ["Manchester United", "Liverpool", "Chelsea", "Arsenal"], "correct": 2},
        {"q": "Who is the all-time top goalscorer for the Argentina national football team?", "options": ["Gabriel Batistuta", "Diego Maradona", "Sergio Agüero", "Lionel Messi"], "correct": 3},
        {"q": "Which iconic stadium is shared by both AC Milan and Inter Milan?", "options": ["Stadio Olimpico", "San Siro", "Gewiss Stadium", "Allianz Stadium"], "correct": 1},
        {"q": "Which player holds the record for the most total appearances in the English Premier League?", "options": ["James Milner", "Frank Lampard", "Gareth Barry", "Ryan Giggs"], "correct": 2},
        {"q": "Which South American country won the Copa América 2024?", "options": ["Colombia", "Brazil", "Uruguay", "Argentina"], "correct": 3},
        {"q": "Who was the manager when Leicester City pulled off their miraculous Premier League win in 2015-16?", "options": ["Nigel Pearson", "Claudio Ranieri", "Brendan Rodgers", "Craig Shakespeare"], "correct": 1},
        {"q": "Which player became the oldest player to ever appear and score in a World Cup match (at age 42)?", "options": ["Roger Milla", "Dino Zoff", "Essam El-Hadary", "Mario Yepes"], "correct": 2},
        {"q": "Which club won the UEFA Europa League in the 2023-24 season?", "options": ["Bayer Leverkusen", "Atalanta", "AS Roma", "Marseille"], "correct": 1},
        {"q": "Which Italian legend is famously nicknamed 'Il Divin Codino' (The Divine Ponytail)?", "options": ["Paolo Maldini", "Francesco Totti", "Alessandro Del Piero", "Roberto Baggio"], "correct": 3},
        {"q": "Which goalkeeper holds the record for the most clean sheets in a single Premier League season (24 clean sheets)?", "options": ["Ederson", "Alisson Becker", "Petr Čech", "Thibaut Courtois"], "correct": 2},
        {"q": "Which legendary Brazil team won the 1970 World Cup and is considered one of the greatest squads ever?", "options": ["Pele & Jairzinho's Brazil", "Romario & Bebeto's Brazil", "Ronaldo & Rivaldo's Brazil", "Zico & Socrates' Brazil"], "correct": 0},
        {"q": "Which player scored the fastest hat-trick in Premier League history (in 2 minutes and 56 seconds)?", "options": ["Sergio Agüero", "Sadio Mané", "Raheem Sterling", "Mohamed Salah"], "correct": 1},
        {"q": "Which Dutch tactical mastermind is credited with pioneering 'Total Football'?", "options": ["Louis van Gaal", "Rinus Michels", "Guus Hiddink", "Ronald Koeman"], "correct": 1},
        {"q": "Which country won the UEFA European Championship in 2016 (Euro 2016)?", "options": ["France", "Portugal", "Germany", "Wales"], "correct": 1},
        {"q": "Who is the all-time leading goalscorer in the history of Real Madrid?", "options": ["Raúl", "Karim Benzema", "Cristiano Ronaldo", "Alfredo Di Stéfano"], "correct": 2},
        {"q": "Which famous stadium is home to Borussia Dortmund and features the legendary 'Yellow Wall'?", "options": ["Allianz Arena", "Signal Iduna Park", "Veltins-Arena", "Deutsche Bank Park"], "correct": 1},
        {"q": "Which young English star won the prestigious Golden Boy award in 2023?", "options": ["Bukayo Saka", "Jude Bellingham", "Jamal Musiala", "Alejandro Garnacho"], "correct": 1},
        {"q": "Which African football legend won both the FIFA World Player of the Year and Ballon d'Or in 1995?", "options": ["Didier Drogba", "Samuel Eto'o", "George Weah", "Yaya Touré"], "correct": 2}
    ]

    q_data = random.choice(questions)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(opt, callback_data=f"trivia_ans_{q_data['correct']}_{i}")] 
        for i, opt in enumerate(q_data["options"])
    ])
    
    await message.reply(f"🧠 **Football Trivia Challenge**\n\n{q_data['q']}", reply_markup=keyboard)


@Client.on_message(filters.command("news"))
async def news_cmd(client: Client, message: Message):
    text = (
        "📰 **Latest Football Transfer & Club Updates**\n\n"
        "• **Global Window Update:** Clubs actively scouting academy prospects for upcoming fixtures.\n"
        "• **Medical Reports:** Fitness assessments completed ahead of weekend matchdays.\n"
        "• **Manager Pressers:** Tactical previews streaming live on official channels.\n"
    )
    await message.reply(text)


@Client.on_callback_query(filters.regex(r"^team_(\d+)$"))
async def team_back_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    await query.answer("Reloading profile...")
    data = await fetch_api("lookupteam.php", {"id": team_id})
    teams = data.get("teams")
    if not teams:
        return await query.answer("Team missing.", show_alert=True)
        
    team = teams[0]
    is_fav = await favorites_db.find_one({"user_id": query.from_user.id, "team_id": team_id}) is not None
    await query.message.delete()
    await send_team_overview(client, query.message.chat.id, team, is_favorite=is_fav)


@Client.on_callback_query(filters.regex(r"^fav_add_(\d+)$"))
async def add_favorite_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    team_req = await fetch_api("lookupteam.php", {"id": team_id})
    if team_req.get("teams"):
        team_name = team_req["teams"][0]["strTeam"]
        await favorites_db.update_one({"user_id": query.from_user.id, "team_id": team_id}, {"$set": {"team_name": team_name}}, upsert=True)
        await query.answer("⭐ Added to favorites!", show_alert=True)
        await team_back_callback(client, query)


@Client.on_callback_query(filters.regex(r"^fav_rem_(\d+)$"))
async def remove_favorite_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    await favorites_db.delete_one({"user_id": query.from_user.id, "team_id": team_id})
    await query.answer("❌ Removed from favorites.", show_alert=True)
    await team_back_callback(client, query)


@Client.on_callback_query(filters.regex(r"^stadium_(\d+)$"))
async def stadium_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    data = await fetch_api("lookupteam.php", {"id": team_id})
    if not data.get("teams"):
        return await query.answer("Data missing.", show_alert=True)
    team = data["teams"][0]
    
    text = (
        f"🏟 **Stadium & Venue Guide**\n\n"
        f"🛡 **Team:** {team.get('strTeam')}\n"
        f"🏟 **Stadium:** {team.get('strStadium')}\n"
        f"📍 **Location:** {team.get('strLocation', 'N/A')}\n"
        f"👥 **Capacity:** {team.get('intStadiumCapacity', 'Unknown')}\n"
        f"🌤 **Climate:** Standard regional conditions."
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"team_{team_id}")]])
    await query.message.reply(text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex(r"^high_(\d+)$"))
async def highlights_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    data = await fetch_api("eventslast.php", {"id": team_id})
    events = data.get("results", [])
    
    text = "🎥 **Post-Match Highlights & Replays**\n\n"
    if not events:
        text += "No highlight reels currently indexed."
    else:
        for e in events[:3]:
            text += f"• **{e.get('strHomeTeam')} vs {e.get('strAwayTeam')}**\n🔗 [Watch Highlights]({e.get('strVideo', 'https://www.thesportsdb.com')})\n\n"
            
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"team_{team_id}")]])
    await query.message.reply(text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex(r"^tv_(\d+)$"))
async def tv_channels_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    await query.answer("Fetching broadcast networks...")
    
    data = await fetch_api("lookuptv.php", {"id": team_id})
    channels = data.get("tvenue", [])
    
    text = "📺 **Official TV Broadcast Channels**\n\n"
    if not channels:
        text += "No specific regional TV listings returned for this team ID."
    else:
        for c in channels[:10]:
            text += f"• {c.get('strChannel')} ({c.get('strCountry', 'Global')})\n"
            
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"team_{team_id}")]])
    await query.message.reply(text, reply_markup=keyboard, parse_mode=None)


@Client.on_callback_query(filters.regex(r"^players_(\d+)$"))
async def players_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    await query.answer("Fetching roster...")
    
    # Correct API endpoint for fetching all players of a team by team ID
    data = await fetch_api("lookup_all_players.php", {"id": team_id})
    players = data.get("player", [])
    
    if not players:
        return await query.message.reply("⚠️ No roster data available for this team ID.", parse_mode=None)
    
    team_req = await fetch_api("lookupteam.php", {"id": team_id})
    team_name = team_req["teams"][0]["strTeam"] if team_req.get("teams") else "Team"
    
    text = f"👕 **{team_name} Roster**\n\n"
    for p in players[:15]:
        text += f"▪️ `{p.get('strPosition', 'N/A')}` - **{p.get('strPlayer')}**\n"
        
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"team_{team_id}")]])
    await query.message.reply(text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex(r"^next_(\d+)$"))
async def next_matches_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    await query.answer("Loading schedule...")
    data = await fetch_api("eventsnext.php", {"id": team_id})
    events = data.get("events")
    
    text = "📅 **Upcoming Fixtures**\n\n"
    if not events:
        text += "No upcoming scheduled fixtures found."
    else:
        for e in events:
            text += f"🏆 **{e.get('strLeague')}**\n⚔️ {e.get('strHomeTeam')} vs {e.get('strAwayTeam')}\n🕒 `{e.get('dateEvent')} • {e.get('strTime', 'TBA')}`\n\n"
        
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"team_{team_id}")]])
    await query.message.reply(text, reply_markup=keyboard, parse_mode=None)


@Client.on_callback_query(filters.regex(r"^past_(\d+)$"))
async def past_matches_callback(client: Client, query: CallbackQuery):
    team_id = query.matches[0].group(1)
    await query.answer("Fetching results...")
    data = await fetch_api("eventslast.php", {"id": team_id})
    events = data.get("results")
    
    text = "🏁 **Recent Results**\n\n"
    if not events:
        text += "No recent match results available."
    else:
        for e in events:
            text += f"📅 `{e.get('dateEvent')}`\n⚽ {e.get('strHomeTeam')} `{e.get('intHomeScore')} - {e.get('intAwayScore')}` {e.get('strAwayTeam')}\n\n"
        
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"team_{team_id}")]])
    await query.message.reply(text, reply_markup=keyboard, parse_mode=None)


@Client.on_callback_query(filters.regex(r"^trivia_ans_([0-3])_([0-3])$"))
async def trivia_answer_callback(client: Client, query: CallbackQuery):
    correct_idx = int(query.matches[0].group(1))
    chosen_idx = int(query.matches[0].group(2))
    
    if correct_idx == chosen_idx:
        await points_db.update_one(
            {"user_id": query.from_user.id},
            {"$inc": {"points": 10}, "$set": {"name": query.from_user.first_name}},
            upsert=True
        )
        await query.answer("🎉 Correct! +10 Points added to your leaderboard standing.", show_alert=True)
    else:
        await query.answer("❌ Incorrect answer! Better luck next time.", show_alert=True)
    await query.message.delete()
