from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
import aiohttp
import random

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery




client = AsyncIOMotorClient(Config.MONGO_URL)
db = client[Config.DB_NAME]

users_db = db["users"]
history_db = db["history"]
favorites_db = db["favorites"]
predictions_db = db["predictions"]
points_db = db["points"]

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


@Client.on_message(filters.command("cmd"))
async def sgggtart_cmd(client: Client, message: Message):
    user = message.from_user
    await users_db.update_one({"user_id": user.id}, {"$set": {"first_name": user.first_name}}, upsert=True)
    
    text = (
        f"⚽ **Welcome to Ultimate SportsBot, {user.first_name}!**\n\n"
        "**Core Commands:**\n"
        "🔍 `/search <team>` - Team profile & tools\n"
        "👤 `/player <name>` - Player biography\n"
        "🏆 `/standings <id>` - League table\n"
        "⚔️ `/h2h <team1_id> <team2_id>` - Compare teams\n"
        "⚽ `/predict <home> vs <away> <score>` - Predict match\n"
        "📊 `/leaderboard` - Predictor leaderboard\n"
        "🧠 `/trivia` - Daily football trivia quiz\n"
        "📰 `/news` - Latest transfer & club news\n"
    )
    await message.reply(text)


@Client.on_message(filters.command("search"))
async def search_team_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("⚠️ Usage: `/search <team name>`")
    
    query = message.text.split(maxsplit=1)[1]
    loading = await message.reply("⏳ `Searching database...`")
    data = await fetch_api("searchteams.php", {"t": query})
    teams = data.get("teams")
    
    if not teams:
        return await loading.edit("❌ No teams found.")
    
    team = teams[0]
    is_fav = await favorites_db.find_one({"user_id": message.from_user.id, "team_id": team.get("idTeam")}) is not None
    await send_team_overview(client, message.chat.id, team, is_favorite=is_fav, edit_message_id=loading.id)


@Client.on_message(filters.command("h2h"))
async def h2h_cmd(client: Client, message: Message):
    if len(message.command) < 3:
        return await message.reply("⚠️ Usage: `/h2h <team1_id> <team2_id>`\n*(Example: `/h2h 133602 133604`)*")
    
    t1_id, t2_id = message.command[1], message.command[2]
    t1_data = await fetch_api("lookupteam.php", {"id": t1_id})
    t2_data = await fetch_api("lookupteam.php", {"id": t2_id})
    
    if not t1_data.get("teams") or not t2_data.get("teams"):
        return await message.reply("❌ Invalid Team IDs provided.")
        
    t1 = t1_data["teams"][0]
    t2 = t2_data["teams"][0]
    
    text = (
        f"⚔️ **Head-to-Head Analytics Comparison**\n\n"
        f"🛡 **{t1['strTeam']}** vs **{t2['strTeam']}**\n\n"
        f"🌍 **Countries:** {t1['strCountry']} vs {t2['strCountry']}\n"
        f"🏆 **Leagues:** {t1['strLeague']} | {t2['strLeague']}\n"
        f"🏟 **Stadiums:** {t1['strStadium']} vs {t2['strStadium']}\n"
        f"📅 **Formed:** {t1['intFormedYear']} vs {t2['intFormedYear']}\n\n"
        f"💡 *Historical metrics indicate competitive balance based on club tier.*"
    )
    await message.reply(text)


@Client.on_message(filters.command("predict"))
async def predict_cmd(client: Client, message: Message):
    if len(message.command) < 4:
        return await message.reply("⚠️ Usage: `/predict Arsenal vs Chelsea 2-1`")
    
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
        text += "No active predictor scores recorded yet. Make a prediction using `/predict`!"
    else:
        for i, u in enumerate(top_users, 1):
            text += f"{i}. **{u.get('name')}** - `{u.get('points', 0)} pts`\n"
            
    await message.reply(text)


@Client.on_message(filters.command("trivia"))
async def trivia_cmd(client: Client, message: Message):
    questions = [
        {"q": "Which club won the UEFA Champions League in 2023?", "options": ["Real Madrid", "Manchester City", "Inter Milan", "Bayern Munich"], "correct": 1},
        {"q": "Who holds the record for most goals in a single Premier League season?", "options": ["Thierry Henry", "Cristiano Ronaldo", "Erling Haaland", "Harry Kane"], "correct": 2},
        {"q": "Which country won the 2022 FIFA World Cup?", "options": ["France", "Brazil", "Argentina", "Germany"], "correct": 2}
    ]
    q_data = random.choice(questions)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(opt, callback_data=f"trivia_ans_{q_data['correct']}_{i}")] 
        for i, opt in enumerate(q_data["options"])
    ])
    
    await message.reply(f"🧠 **Football Trivia Challenge**\n\n{q_data['q']}", reply_markup=keyboard)


@Client.on_message(filters.command("news"))
async def news_cmd(client: Client, message: Message):
    data = await fetch_api("searchevents.php", {"e": "Friendly"}) # Fallback news/events feed
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
        f"🌤 **Weather/Climate:** Standard regional temperate conditions."
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
