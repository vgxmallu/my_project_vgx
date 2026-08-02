import aiohttp
from config import Config
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from pyrogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent


    



class AniListAPI:
    async def _request(self, query: str, variables: dict = None) -> dict:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(Config.GRAPHQL_URL, json={"query": query, "variables": variables or {}}, headers=headers) as resp:
                data = await resp.json()
                return data.get("data", {})


        async def get_media(self, search: str = None, media_id: int = None, m_type: str = "ANIME") -> dict:
        query = """
        query ($search: String, $id: Int, $type: MediaType) {
          Media (search: $search, id: $id, type: $type) {
            id title { romaji english native } synonyms
            format episodes duration status
            startDate { year month day } endDate { year month day }
            season seasonYear averageScore meanScore popularity favourites
            source hashtag genres description(asHtml: false)
            coverImage { extraLarge } siteUrl
            trailer { id site }
            studios { edges { isMain node { name isAnimationStudio } } }
            characters(sort: ROLE, perPage: 6) { edges { role node { name { full } } } }
          }
        }
        """
        variables = {"type": m_type}
        if media_id: variables["id"] = media_id
        if search: variables["search"] = search
        
        response = await self._request(query, variables)
        
        # FIX: Ensure response is not None before calling .get()
        if not response:
            return {}
            
        return response.get("Media") or {}


        async def get_character(self, search: str) -> dict:
        query = """
        query ($search: String) {
          Character (search: $search) {
            name { full native } image { large } gender age bloodType 
            description(asHtml: false) siteUrl
          }
        }
        """
        response = await self._request(query, {"search": search})
        if not response:
            return {}
        return response.get("Character") or {}

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
        response = await self._request(query)
        if not response:
            return []
        page = response.get("Page")
        if not page:
            return []
        return page.get("airingSchedules") or []

    async def get_user(self, name: str) -> dict:
        query = """
        query ($name: String) {
          User (name: $name) {
            name avatar { large } siteUrl
            statistics { anime { count meanScore } manga { count meanScore } }
          }
        }
        """
        response = await self._request(query, {"name": name})
        if not response:
            return {}
        return response.get("User") or {}

api = AniListAPI()


def clean_html(text: str) -> str:
    if not text: return "No description available."
    # Remove standard HTML breaks returned by AniList
    text = text.replace("<br>", "\n").replace("<i>", "").replace("</i>", "")
    return text[:900] + "..." if len(text) > 900 else text

    
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


@Client.on_message(filters.command(["anime", "manga"]))
async def cmd_media(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(f"**Usage:** `/{message.command[0]} [title]`")
    
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
    if len(message.command) < 2: return await message.reply_text("Usage: `/character [name]`")
    
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
    if len(message.command) < 2: return await message.reply_text("Usage: `/user [username]`")
    
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


#====================================================
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def media_tabs_kb(media_id: int, current_tab: str, trailer: dict = None, url: str = None) -> InlineKeyboardMarkup:
    """
    Generates the UI buttons. Highlights the active tab with a ✅.
    """
    stats_btn = "✅ Statistics" if current_tab == "stats" else "📊 Statistics"
    synops_btn = "✅ Synopsis" if current_tab == "synopsis" else "📝 Synopsis"
    chars_btn = "✅ Characters" if current_tab == "chars" else "👥 Characters"

    buttons = [
        [
            InlineKeyboardButton(stats_btn, callback_data=f"stats_{media_id}"),
            InlineKeyboardButton(synops_btn, callback_data=f"synopsis_{media_id}")
        ],
        [
            InlineKeyboardButton(chars_btn, callback_data=f"chars_{media_id}")
        ]
    ]
    
    links = []
    if trailer and trailer.get("site") == "youtube":
        links.append(InlineKeyboardButton("🎬 Trailer", url=f"https://youtube.com/watch?v={trailer.get('id')}"))
    if url:
        links.append(InlineKeyboardButton("🌐 AniList", url=url))
        
    if links:
        buttons.append(links)
        
    return InlineKeyboardMarkup(buttons)

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.types import CallbackQuery


def build_stats_text(data: dict) -> str:
    """Generates the deeply detailed Frieren-style stats page."""
    t = data.get('title', {})
    start_d, end_d = format_date(data.get('startDate')), format_date(data.get('endDate'))
    studios, producers = parse_studios(data.get('studios', {}).get('edges', []))
    
    text = f"📺 **{t.get('romaji')}**\n"
    if t.get('english'): text += f"**🇬🇧** {t.get('english')}\n"
    if t.get('native'): text += f"**🇯🇵** {t.get('native')}\n\n"
    
    text += f"**Format:** {data.get('format', 'N/A')}\n"
    text += f"**Episodes:** {data.get('episodes', 'N/A')}\n"
    text += f"**Episode Duration:** {data.get('duration', 'N/A')} mins\n"
    text += f"**Status:** {data.get('status', 'N/A')}\n"
    text += f"**Start Date:** {start_d}\n"
    text += f"**End Date:** {end_d}\n"
    if data.get('season'):
        text += f"**Season:** {data.get('season').capitalize()} {data.get('seasonYear')}\n"
    text += f"**Average Score:** {data.get('averageScore', 'N/A')}%\n"
    text += f"**Popularity:** {data.get('popularity', 'N/A')} | **Favorites:** {data.get('favourites', 'N/A')}\n\n"
    
    text += f"🎬 **Studios:** {studios}\n"
    text += f"🏢 **Producers:** {producers}\n"
    text += f"📖 **Source:** {data.get('source', 'N/A').replace('_', ' ').capitalize()}\n"
    text += f"🎭 **Genres:** {', '.join(data.get('genres', []))}"
    return text

@Client.on_message(filters.command(["aanime"]))
async def cmd_heanime(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(f"**Usage:** `/{message.command[0]} title`")
    
    m_type = "ANIME" if message.command[0] == "anime" else "MANGA"
    msg = await message.reply_text("🔎 Fetching data...")
    
    data = await api.get_media(search=" ".join(message.command[1:]), m_type=m_type)
    if not data:
        return await msg.edit_text("❌ Media not found.")

    text = build_stats_text(data)
    kb = media_tabs_kb(data["id"], "stats", data.get("trailer"), data.get("siteUrl"))
    img = data.get('coverImage', {}).get('extraLarge')
    
    await msg.delete()
    if img:
        await message.reply_photo(img, caption=text[:1024], reply_markup=kb)
    else:
        await message.reply_text(text, reply_markup=kb)



@Client.on_callback_query(filters.regex(r"^media_(stats|synopsis|chars)_(\d+)$"))
async def on_callback(client: Client, query: CallbackQuery):
    # Extract action and media_id cleanly using regex match groups
    _, action, media_id_str = query.matches[0].groups()
    media_id = int(media_id_str)
    
    # Let Telegram know we received the click
    await query.answer()

    # Re-fetch data using the ID
    data = await api.get_media(media_id=media_id)
    if not data:
        return await query.answer("❌ Error fetching data.", show_alert=True)

    t = data.get('title', {})
    header = f"📺 **{t.get('romaji')}**\n\n"
    
    # 1. STATISTICS TAB
    if action == "stats":
        text = build_stats_text(data)
        
    # 2. SYNOPSIS TAB
    elif action == "synopsis":
        desc = clean_html(data.get("description"))
        text = header + f"📝 **Synopsis:**\n\n{desc}"
        
    # 3. CHARACTERS TAB
    elif action == "chars":
        chars = data.get("characters", {}).get("edges", [])
        if not chars:
            text = header + "❌ No character data available."
        else:
            text = header + "👥 **Main Characters:**\n\n"
            for edge in chars:
                role = edge.get("role")
                name = edge.get("node", {}).get("name", {}).get("full")
                text += f"▪️ **{name}** ({role})\n"
    else:
        return

    # Generate the updated keyboard (highlights the active tab)
    kb = media_tabs_kb(media_id, action, data.get("trailer"), data.get("siteUrl"))
    
    # Update the message gracefully
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=text[:1024], reply_markup=kb)
        else:
            await query.edit_message_text(text=text[:1024], reply_markup=kb)
    except Exception:
        pass # Ignore errors if the user clicks the same button twice
