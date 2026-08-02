import aiohttp
from config import Config

class AniListAPI:
    async def _request(self, query: str, variables: dict = None) -> dict:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(Config.GRAPHQL_URL, json={"query": query, "variables": variables or {}}, headers=headers) as resp:
                data = await resp.json()
                return data.get("data", {})

    async def get_media(self, search: str, m_type: str = "ANIME") -> dict:
        query = """
        query ($search: String, $type: MediaType) {
          Media (search: $search, type: $type) {
            id title { romaji english native } synonyms
            format episodes duration status
            startDate { year month day } endDate { year month day }
            season seasonYear averageScore meanScore popularity favourites
            source hashtag genres description(asHtml: false)
            coverImage { extraLarge } bannerImage siteUrl
            studios { edges { isMain node { name isAnimationStudio } } }
          }
        }
        """
        data = await self._request(query, {"search": search, "type": m_type})
        return data.get("Media", {})

    async def get_character(self, search: str) -> dict:
        query = """
        query ($search: String) {
          Character (search: $search) {
            name { full native } image { large } gender age bloodType 
            description(asHtml: false) siteUrl
          }
        }
        """
        data = await self._request(query, {"search": search})
        return data.get("Character", {})

    async def get_schedules(self) -> list:
        query = """
        query {
          Page(page: 1, perPage: 10) {
            airingSchedules(notYetAiring: true, sort: TIME) {
              episode timeUntilAiring media { title { romaji } }
            }
          }
        }
        """
        data = await self._request(query)
        return data.get("Page", {}).get("airingSchedules", [])

    async def get_user(self, name: str) -> dict:
        query = """
        query ($name: String) {
          User (name: $name) {
            name avatar { large } siteUrl
            statistics { anime { count meanScore } manga { count meanScore } }
          }
        }
        """
        data = await self._request(query, {"name": name})
        return data.get("User", {})

api = AniListAPI()

def format_date(date_dict: dict) -> str:
    """Safely converts AniList date dict to a readable string."""
    if not date_dict or not date_dict.get('year'):
        return "Unknown"
    
    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    y = date_dict.get('year')
    m = date_dict.get('month')
    d = date_dict.get('day')
    
    if y and m and d: return f"{months[m]} {d}, {y}"
    if y and m: return f"{months[m]} {y}"
    return str(y)

def parse_studios(edges: list) -> tuple:
    """Separates Main Studios from Producers."""
    studios, producers = [], []
    for edge in edges:
        node = edge.get("node", {})
        if node.get("isAnimationStudio"):
            studios.append(node.get("name"))
        else:
            producers.append(node.get("name"))
    return ", ".join(studios) or "None", ", ".join(producers) or "None"

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.command(["anime", "manga"]))
async def cmd_media(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(f"**Usage:** `/{message.command[0]} <title>`")
    
    m_type = "ANIME" if message.command[0] == "anime" else "MANGA"
    msg = await message.reply_text("🔎 Fetching data...")
    data = await api.get_media(" ".join(message.command[1:]), m_type)
    
    if not data:
        return await msg.edit_text("❌ Media not found.")

    t = data.get('title', {})
    start_d = format_date(data.get('startDate'))
    end_d = format_date(data.get('endDate'))
    studios, producers = parse_studios(data.get('studios', {}).get('edges', []))
    
    text = f"**{t.get('romaji')}**\n"
    if t.get('english'): text += f"**English:** {t.get('english')}\n"
    if t.get('native'): text += f"**Native:** {t.get('native')}\n"
    
    synonyms = ", ".join(data.get('synonyms', []))
    if synonyms: text += f"**Synonyms:** {synonyms}\n"
    
    text += "\n"
    text += f"▪️ **Format:** {data.get('format', 'N/A')}\n"
    text += f"▪️ **Episodes:** {data.get('episodes', 'N/A')}\n"
    text += f"▪️ **Episode Duration:** {data.get('duration', 'N/A')} mins\n"
    text += f"▪️ **Status:** {data.get('status', 'N/A')}\n"
    text += f"▪️ **Start Date:** {start_d}\n"
    text += f"▪️ **End Date:** {end_d}\n"
    
    if data.get('season'):
        text += f"▪️ **Season:** {data.get('season').capitalize()} {data.get('seasonYear')}\n"
        
    text += f"▪️ **Average Score:** {data.get('averageScore', 'N/A')}%\n"
    text += f"▪️ **Mean Score:** {data.get('meanScore', 'N/A')}%\n"
    text += f"▪️ **Popularity:** {data.get('popularity', 'N/A')}\n"
    text += f"▪️ **Favorites:** {data.get('favourites', 'N/A')}\n\n"
    
    text += f"🎬 **Studios:** {studios}\n"
    text += f"🏢 **Producers:** {producers}\n"
    text += f"📖 **Source:** {data.get('source', 'N/A').replace('_', ' ').capitalize()}\n"
    
    if data.get('hashtag'): text += f"🏷️ **Hashtag:** {data.get('hashtag')}\n"
    text += f"🎭 **Genres:** {', '.join(data.get('genres', []))}\n"

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌐 View on AniList", url=data.get('siteUrl'))]])
    img = data.get('coverImage', {}).get('extraLarge')
    
    await msg.delete()
    if img:
        await message.reply_photo(img, caption=text[:1024], reply_markup=kb) # Caption limits apply
    else:
        await message.reply_text(text, reply_markup=kb)

from pyrogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

@Client.on_inline_query()
async def inline_search(client: Client, query: InlineQuery):
    if not query.query:
        return
        
    data = await api.get_media(query.query, "ANIME")
    if not data:
        return

    title = data.get("title", {}).get("romaji", "Unknown")
    score = data.get("averageScore", "N/A")
    episodes = data.get("episodes", "?")
    url = data.get("siteUrl", "")
    
    text = f"📺 **{title}**\n▪️ Episodes: {episodes} | Score: {score}%\n🔗 {url}"

    results = [
        InlineQueryResultArticle(
            title=title,
            description=f"Format: {data.get('format')} | Score: {score}%",
            thumb_url=data.get('coverImage', {}).get('extraLarge'),
            input_message_content=InputTextMessageContent(text)
        )
    ]
    
    await query.answer(results, cache_time=5)


from pyrogram.types import Message

@Client.on_message(filters.command("airing"))
async def cmd_airing(client: Client, message: Message):
    schedules = await api.get_schedules()
    if not schedules: return await message.reply_text("❌ No data available.")

    text = "📡 **Upcoming Episode Airings**\n\n"
    for item in schedules:
        title = item.get('media', {}).get('title', {}).get('romaji')
        hrs = item.get('timeUntilAiring', 0) / 3600
        text += f"▪️ **{title}**\n   ↳ Ep {item.get('episode')} airs in **{hrs:.1f} hours**\n\n"
        
    await message.reply_text(text)

@Client.on_message(filters.command("character"))
async def cmd_character(client: Client, message: Message):
    if len(message.command) < 2: return await message.reply_text("Usage: `/character <name>`")
    
    data = await api.get_character(" ".join(message.command[1:]))
    if not data: return await message.reply_text("❌ Not found.")

    name = data.get('name', {}).get('full', 'Unknown')
    text = f"👤 **{name}**\n\n▪️ **Gender:** {data.get('gender', 'N/A')}\n▪️ **Age:** {data.get('age', 'N/A')}\n▪️ **Blood Type:** {data.get('bloodType', 'N/A')}"
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Profile", url=data.get('siteUrl'))]])
    img = data.get('image', {}).get('large')
    
    if img: await message.reply_photo(img, caption=text, reply_markup=kb)
    else: await message.reply_text(text, reply_markup=kb)


@Client.on_message(filters.command("user"))
async def cmd_user(client: Client, message: Message):
    if len(message.command) < 2: return await message.reply_text("Usage: `/user <username>`")
    
    data = await api.get_user(message.command[1])
    if not data: return await message.reply_text("❌ User not found.")

    stats = data.get("statistics", {})
    text = (
        f"📊 **AniList Profile: {data.get('name')}**\n\n"
        f"📺 **Anime:** {stats.get('anime', {}).get('count')} (Mean Score: {stats.get('anime', {}).get('meanScore')}%)\n"
        f"📖 **Manga:** {stats.get('manga', {}).get('count')} (Mean Score: {stats.get('manga', {}).get('meanScore')}%)"
    )
    
    img = data.get('avatar', {}).get('large')
    if img: await message.reply_photo(img, caption=text)
    else: await message.reply_text(text)
