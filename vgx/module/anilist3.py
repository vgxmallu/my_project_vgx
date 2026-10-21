import aiohttp

GRAPHQL_URL = "https://graphql.anilist.co"

# --- GraphQL Queries ---
ANIME_SEARCH_QUERY = """
query ($search: String) {
  Media (search: $search, type: ANIME) {
    id
    title { romaji english }
    episodes
    status
    averageScore
    genres
    description(asHtml: false)
    coverImage { large }
    siteUrl
  }
}
"""

MANGA_SEARCH_QUERY = """
query ($search: String) {
  Media (search: $search, type: MANGA) {
    id
    title { romaji english }
    chapters
    volumes
    status
    averageScore
    genres
    description(asHtml: false)
    coverImage { large }
    siteUrl
  }
}
"""

CHARACTER_SEARCH_QUERY = """
query ($search: String) {
  Character (search: $search) {
    id
    name { full native }
    description(asHtml: false)
    image { large }
    siteUrl
  }
}
"""

USER_SEARCH_QUERY = """
query ($search: String) {
  User (name: $search) {
    id
    name
    about(asHtml: false)
    avatar { large }
    siteUrl
    statistics {
      anime { count episodesWatched meanScore }
      manga { count chaptersRead meanScore }
    }
  }
}
"""

TRENDING_ANIME_QUERY = """
query {
  Page(page: 1, perPage: 5) {
    media(sort: TRENDING_DESC, type: ANIME) {
      id
      title { english romaji }
      averageScore
    }
  }
}
"""

AIRING_SCHEDULE_QUERY = """
query ($startDay: Int, $endDay: Int) {
  Page (page: 1, perPage: 10) {
    airingSchedules (airingAt_greater: $startDay, airingAt_lesser: $endDay, sort: TIME_ASC) {
      episode
      airingAt
      media {
        id
        title { english romaji }
        coverImage { large }
      }
    }
  }
}
"""

RECOMMENDATION_QUERY = """
query ($page: Int) {
  Page (page: $page, perPage: 5) {
    media (sort: SCORE_DESC, type: ANIME) {
      id
      title { english romaji }
      averageScore
      genres
      coverImage { large }
      siteUrl
    }
  }
}
"""



async def fetch_anilist(query: str, variables: dict = None) -> dict:
    """Asynchronously queries the AniList GraphQL API."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
        
    async with aiohttp.ClientSession() as session:
        async with session.post(GRAPHQL_URL, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", {})
            return {}

#====================================================

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
from vgx.database.anilist_db import db

import re
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import time
from datetime import datetime, timezone

def clean_html(raw_html: str) -> str:
    """Removes HTML tags from descriptions for clean Telegram markup."""
    if not raw_html:
        return "N/A"
    clean_text = re.sub(r'<[^>]+>', '', raw_html)
    return (clean_text[:280] + "...") if len(clean_text) > 300 else clean_text

@Client.on_message(filters.command("anime3"))
async def search_affnime(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/anime title`")
        
    query_title = " ".join(message.command[1:])
    msg = await message.reply_text("🔍 Searching AniList...")
    
    result = await fetch_anilist(ANIME_SEARCH_QUERY, {"search": query_title})
    media = result.get("Media")
    
    if not media:
        return await msg.edit_text("❌ No anime found on AniList.")
        
    anime_id = media["id"]
    title = media["title"].get("english") or media["title"].get("romaji") or "Unknown"
    episodes = media.get("episodes") or "N/A"
    status = media.get("status") or "N/A"
    score = media.get("averageScore") or "N/A"
    genres = ", ".join(media.get("genres", [])) or "N/A"
    desc = clean_html(media.get("description"))
    cover = media["coverImage"].get("large")
    site_url = media.get("siteUrl")
    
    # Store collected anime in MongoDB
    await db.collected_items.update_one(
        {"item_id": anime_id, "type": "anime"},
        {"$set": {"title": title, "score": score}},
        upsert=True
    )
    
    caption = (
        f"⛩️ **{title}**\n\n"
        f"📊 **Score:** `{score}%` | 📺 **Episodes:** `{episodes}`\n"
        f"📌 **Status:** `{status}`\n"
        f"🏷️ **Genres:** `{genres}`\n\n"
        f"📖 **Synopsis:**\n{desc}"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ Favourite", callback_data=f"anilist_fav_anime_{anime_id}"),
            InlineKeyboardButton("🔗 View on AniList", url=site_url)
        ]
    ])
    
    if cover:
        await message.reply_photo(photo=cover, caption=caption, reply_markup=keyboard)
        await msg.delete()
    else:
        await msg.edit_text(caption, reply_markup=keyboard)

@Client.on_message(filters.command("manga3"))
async def search_macgnga(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/manga title`")
        
    query_title = " ".join(message.command[1:])
    msg = await message.reply_text("🔍 Searching AniList for Manga...")
    
    result = await fetch_anilist(MANGA_SEARCH_QUERY, {"search": query_title})
    media = result.get("Media")
    
    if not media:
        return await msg.edit_text("❌ No manga found on AniList.")
        
    manga_id = media["id"]
    title = media["title"].get("english") or media["title"].get("romaji") or "Unknown"
    chapters = media.get("chapters") or "N/A"
    volumes = media.get("volumes") or "N/A"
    status = media.get("status") or "N/A"
    score = media.get("averageScore") or "N/A"
    cover = media["coverImage"].get("large")
    site_url = media.get("siteUrl")
    
    await db.collected_items.update_one(
        {"item_id": manga_id, "type": "manga"},
        {"$set": {"title": title, "score": score}},
        upsert=True
    )
    
    caption = (
        f"📚 **{title}**\n\n"
        f"📊 **Score:** `{score}%` | 📖 **Chapters:** `{chapters}` | 📑 **Volumes:** `{volumes}`\n"
        f"📌 **Status:** `{status}`"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ Favourite", callback_data=f"anilist_fav_manga_{manga_id}"),
            InlineKeyboardButton("🔗 View on AniList", url=site_url)
        ]
    ])
    
    if cover:
        await message.reply_photo(photo=cover, caption=caption, reply_markup=keyboard)
        await msg.delete()
    else:
        await msg.edit_text(caption, reply_markup=keyboard)

@Client.on_message(filters.command("character3"))
async def search_charccacter(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/character name`")
        
    query_name = " ".join(message.command[1:])
    msg = await message.reply_text("🔍 Searching character...")
    
    result = await fetch_anilist(CHARACTER_SEARCH_QUERY, {"search": query_name})
    char = result.get("Character")
    
    if not char:
        return await msg.edit_text("❌ Character not found.")
        
    char_id = char["id"]
    name_full = char["name"].get("full")
    name_native = char["name"].get("native") or ""
    desc = clean_html(char.get("description"))
    image = char["image"].get("large")
    site_url = char.get("siteUrl")
    
    caption = (
        f"👤 **{name_full}** (`{name_native}`)\n\n"
        f"📝 **About:**\n{desc}"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ Favourite", callback_data=f"anilist_fav_char_{char_id}"),
            InlineKeyboardButton("🔗 View on AniList", url=site_url)
        ]
    ])
    
    if image:
        await message.reply_photo(photo=image, caption=caption, reply_markup=keyboard)
        await msg.delete()
    else:
        await msg.edit_text(caption, reply_markup=keyboard)

@Client.on_message(filters.command("user3"))
async def searchff_user(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/user anilist_username`")
        
    username = message.command[1]
    msg = await message.reply_text("🔍 Fetching AniList Profile...")
    
    result = await fetch_anilist(USER_SEARCH_QUERY, {"search": username})
    user = result.get("User")
    
    if not user:
        return await msg.edit_text("❌ User profile not found on AniList.")
        
    name = user["name"]
    avatar = user["avatar"].get("large")
    site_url = user.get("siteUrl")
    
    anime_stats = user.get("statistics", {}).get("anime", {})
    manga_stats = user.get("statistics", {}).get("manga", {})
    
    caption = (
        f"👤 **AniList Profile:** `{name}`\n\n"
        f"📺 **Anime Stats:**\n"
        f"• Total Watched: `{anime_stats.get('count', 0)}`\n"
        f"• Episodes Watched: `{anime_stats.get('episodesWatched', 0)}`\n"
        f"• Mean Score: `{anime_stats.get('meanScore', 0)}%`\n\n"
        f"📚 **Manga Stats:**\n"
        f"• Total Read: `{manga_stats.get('count', 0)}`\n"
        f"• Chapters Read: `{manga_stats.get('chaptersRead', 0)}`\n"
        f"• Mean Score: `{manga_stats.get('meanScore', 0)}%`"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Open AniList Profile", url=site_url)]
    ])
    
    if avatar:
        await message.reply_photo(photo=avatar, caption=caption, reply_markup=keyboard)
        await msg.delete()
    else:
        await msg.edit_text(caption, reply_markup=keyboard)

@Client.on_message(filters.command("trending"))
async def trending_anffime(client: Client, message: Message):
    msg = await message.reply_text("🔥 Fetching trending anime...")
    
    result = await fetch_anilist(TRENDING_ANIME_QUERY)
    media_list = result.get("Page", {}).get("media", [])
    
    if not media_list:
        return await msg.edit_text("❌ Could not fetch trending list.")
        
    text = "🔥 **Top Trending Anime Right Now:**\n\n"
    for idx, anime in enumerate(media_list, 1):
        title = anime["title"].get("english") or anime["title"].get("romaji")
        score = anime.get("averageScore", "N/A")
        text += f"{idx}. **{title}** — ⭐ `{score}%`\n"
        
    await msg.edit_text(text)

@Client.on_message(filters.command("anistats") & filters.private)
async def global_staffts(client: Client, message: Message):
    total_collected = await db.collected_items.count_documents({})
    total_favs = await db.favorites.count_documents({})
    
    text = (
        "📈 **AniList Bot System Statistics**\n\n"
        f"📚 **Total Media Cached:** `{total_collected}`\n"
        f"⭐ **Total Saved Favourites:** `{total_favs}`"
    )
    await message.reply_text(text)


@Client.on_message(filters.command("anischedule"))
async def airing_schedggule(client: Client, message: Message):
    msg = await message.reply_text("🗓️ Fetching today's airing schedule...")
    
    # Get current UTC timestamps for today's window
    now = datetime.now(timezone.utc)
    start_timestamp = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    end_timestamp = start_timestamp + 86400  # End of the day
    
    data = await fetch_anilist(AIRING_SCHEDULE_QUERY, {"startDay": start_timestamp, "endDay": end_timestamp})
    schedules = data.get("Page", {}).get("airingSchedules", [])
    
    if not schedules:
        return await msg.edit_text("❌ No anime episodes scheduled for today.")
        
    text = "🗓️ **Today's Airing Schedule (UTC):**\n\n"
    for item in schedules:
        anime = item.get("media", {})
        title = anime["title"].get("english") or anime["title"].get("romaji")
        episode = item["episode"]
        air_time = datetime.fromtimestamp(item["airingAt"], timezone.utc).strftime("%H:%M")
        text += f"⏰ `{air_time}` — **{title}** (Ep `{episode}`)\n"
        
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh Schedule", callback_data="anilist_sched_refresh")]
    ])
    
    await msg.edit_text(text, reply_markup=keyboard)

@Client.on_message(filters.command("anirecommend"))
async def recommend_anigvme(client: Client, message: Message):
    msg = await message.reply_text("✨ Generating top recommendations...")
    
    data = await fetch_anilist(RECOMMENDATION_QUERY, {"page": 1})
    media_list = data.get("Page", {}).get("media", [])
    
    if not media_list:
        return await msg.edit_text("❌ Could not fetch recommendations.")
        
    # Pick the first recommendation to display with an image card
    anime = media_list[0]
    anime_id = anime["id"]
    title = anime["title"].get("english") or anime["title"].get("romaji")
    score = anime.get("averageScore", "N/A")
    genres = ", ".join(anime.get("genres", []))
    cover = anime["coverImage"].get("large")
    site_url = anime.get("siteUrl")
    
    caption = (
        f"🌟 **Top Recommendation:**\n\n"
        f"⛩️ **{title}**\n"
        f"📊 **Score:** `{score}%`\n"
        f"🏷️ **Genres:** `{genres}`"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ Favourite", callback_data=f"anilist_fav_anime_{anime_id}"),
            InlineKeyboardButton("🔗 Open AniList", url=site_url)
        ]
    ])
    
    if cover:
        await message.reply_photo(photo=cover, caption=caption, reply_markup=keyboard)
        await msg.delete()
    else:
        await msg.edit_text(caption, reply_markup=keyboard)

@Client.on_message(filters.command("anitopstats"))
async def leaderboagfrd_stats(client: Client, message: Message):
    # Aggregate top users by favourite count from MongoDB
    pipeline = [
        {"$group": {"_id": "$username", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    
    top_users = await db.favorites.aggregate(pipeline).to_list(length=5)
    
    text = "🏆 **Collector Leaderboard (Top Users):**\n\n"
    if not top_users:
        text += "No favourites saved yet! Be the first by using `/anime`."
    else:
        for idx, user in enumerate(top_users, 1):
            name = user["_id"] or "Anonymous"
            count = user["count"]
            text += f"{idx}. **{name}** — `{count}` favourites\n"
            
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Main Menu", callback_data="anilist_home")]
    ])
    
    await message.reply_text(text, reply_markup=keyboard)


#====================================================



# Callback regex pattern matching item type and ID: anilist_fav_{type}_{id}
@Client.on_callback_query(filters.regex(r"^anilist_fav_(anime|manga|char)_(\d+)$"))
async def handle_favourite_callbavck(client: Client, query: CallbackQuery):
    item_type = query.matches[0].group(1)
    item_id = int(query.matches[0].group(2))
    
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    update_result = await db.favorites.update_one(
        {"user_id": user_id, "item_id": item_id, "item_type": item_type},
        {"$set": {"username": username}},
        upsert=True
    )
    
    if update_result.upserted_id or update_result.modified_count > 0:
        await query.answer(f"⭐ Added {item_type.upper()} to your favourites!", show_alert=True)
    else:
        await query.answer(f"ℹ️ Already in your favourites!", show_alert=True)
      
