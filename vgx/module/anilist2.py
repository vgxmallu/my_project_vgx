import aiohttp
from config import Config
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery



class AniListAPI:
    def __init__(self):
        self.url = Config.GRAPHQL_URL
        self.client_id = Config.ANILIST_CLIENT_ID
        self.client_secret = Config.ANILIST_CLIENT_SECRET

    async def _request(self, query: str, variables: dict = None, access_token: str = None) -> dict:
        """Core request handler supporting optional OAuth2 Bearer tokens."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # If an access token is provided, authorize the request
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
            
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, json={"query": query, "variables": variables}, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get("data", {})
                    if response:
                        return response
                return {}

    async def get_media(self, search: str = None, media_id: int = None, m_type: str = "ANIME") -> dict:
        """Fetches detailed Anime/Manga information."""
        query = """
        query ($search: String, $id: Int, $type: MediaType) {
          Media (search: $search, id: $id, type: $type) {
            id type format episodes duration status
            startDate { year month day } endDate { year month day }
            season seasonYear averageScore meanScore popularity favourites
            source hashtag genres description(asHtml: false)
            title { romaji english native } synonyms
            coverImage { extraLarge } siteUrl
            trailer { id site }
            studios(isMain: true) { edges { node { name } } }
            producers: studios(isMain: false) { edges { node { name } } }
            characters(sort: ROLE, perPage: 10) { edges { role node { name { full } } } }
          }
        }
        """
        variables = {"type": m_type}
        if media_id: variables["id"] = media_id
        if search: variables["search"] = search
        
        response = await self._request(query, variables)
        return response.get("Media") or {}

api = AniListAPI()

#====================================================

def format_date(date_dict: dict) -> str:
    if not date_dict or not date_dict.get('year'): return "Unknown"
    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    y, m, d = date_dict.get('year'), date_dict.get('month'), date_dict.get('day')
    if y and m and d: return f"{months[m]} {d}, {y}"
    if y and m: return f"{months[m]} {y}"
    return str(y)

def build_info_text(data: dict) -> str:
    t = data.get('title', {})
    studios = [edge['node']['name'] for edge in data.get('studios', {}).get('edges', [])]
    producers = [edge['node']['name'] for edge in data.get('producers', {}).get('edges', [])]
    
    text = f"📺 **{t.get('romaji', 'Unknown')}**\n"
    if t.get('english'): text += f"🇬🇧 **English:** {t.get('english')}\n"
    if t.get('native'): text += f"🇯🇵 **Native:** {t.get('native')}\n"
    
    synonyms = data.get('synonyms', [])
    if synonyms: text += f"🔖 **Synonyms:** {', '.join(synonyms[:2])}\n"
        
    text += "\n"
    text += f"**Format:** {data.get('format', 'N/A')} | **Status:** {data.get('status', 'N/A')}\n"
    text += f"**Episodes:** {data.get('episodes', 'N/A')} | **Duration:** {data.get('duration', 'N/A')} mins\n"
    text += f"**Start Date:** {format_date(data.get('startDate'))}\n"
    text += f"**End Date:** {format_date(data.get('endDate'))}\n"
    
    if data.get('season'):
        text += f"**Season:** {data.get('season').capitalize()} {data.get('seasonYear')}\n"
        
    text += f"**Average Score:** {data.get('averageScore', 'N/A')}% | **Mean Score:** {data.get('meanScore', 'N/A')}%\n"
    text += f"**Popularity:** {data.get('popularity', 'N/A')} | **Favorites:** {data.get('favourites', 'N/A')}\n"
    text += f"**Source:** {data.get('source', 'N/A').replace('_', ' ').capitalize()}\n"
    if data.get('hashtag'): text += f"**Hashtag:** {data.get('hashtag')}\n"
    text += f"**Genres:** {', '.join(data.get('genres', []))}\n\n"
    text += f"🎬 **Studios:** {', '.join(studios) if studios else 'N/A'}\n"
    text += f"🏢 **Producers:** {', '.join(producers[:4]) if producers else 'N/A'}"
    
    return text[:1024]

#====================================================

def get_keyboard(media_id: int, current_tab: str, trailer: dict = None, url: str = None) -> InlineKeyboardMarkup:
    btn_info = "✅ Info" if current_tab == "info" else "📊 Info"
    btn_syn = "✅ Synopsis" if current_tab == "syn" else "📝 Synopsis"
    btn_char = "✅ Characters" if current_tab == "char" else "👥 Characters"

    buttons = [
        [
            InlineKeyboardButton(btn_info, callback_data=f"ani_info_{media_id}"),
            InlineKeyboardButton(btn_syn, callback_data=f"ani_syn_{media_id}")
        ],
        [
            InlineKeyboardButton(btn_char, callback_data=f"ani_char_{media_id}")
        ]
    ]
    
    links = []
    if trailer and trailer.get("site") == "youtube":
        links.append(InlineKeyboardButton("🎬 Trailer", url=f"https://youtube.com/watch?v={trailer.get('id')}"))
    if url:
        links.append(InlineKeyboardButton("🌐 AniList", url=url))
        
    if links: buttons.append(links)
    return InlineKeyboardMarkup(buttons)

#====================================================

@Client.on_message(filters.command(["anime", "manga"]))
async def search_media(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(f"**Usage:** `/{message.command[0]} <name>`")
    
    query = " ".join(message.command[1:])
    m_type = "ANIME" if message.command[0] == "anime" else "MANGA"
    msg = await message.reply_text("🔎 **Searching AniList...**")
    
    data = await api.get_media(search=query, m_type=m_type)
    if not data:
        return await msg.edit_text("❌ **No results found!**")

    text = build_info_text(data)
    kb = get_keyboard(data["id"], "info", data.get("trailer"), data.get("siteUrl"))
    img = data.get('coverImage', {}).get('extraLarge')
    
    await msg.delete()
    if img:
        await message.reply_photo(img, caption=text, reply_markup=kb)
    else:
        await message.reply_text(text, reply_markup=kb)

@Client.on_callback_query(filters.regex(r"^ani_(info|syn|char)_(\d+)$"))
async def handle_tabs(client: Client, query: CallbackQuery):
    tab, media_id_str = query.matches[0].groups()
    media_id = int(media_id_str)
    
    await query.answer()
    data = await api.get_media(media_id=media_id)
    if not data:
        return await query.answer("❌ Failed to fetch data.", show_alert=True)

    header = f"📺 **{data.get('title', {}).get('romaji')}**\n\n"
    
    if tab == "info":
        text = build_info_text(data)
    elif tab == "syn":
        desc = data.get("description", "No description available.").replace("<br>", "\n").replace("<i>", "").replace("</i>", "")
        text = header + f"📝 **Synopsis:**\n\n{desc}"
    elif tab == "char":
        chars = data.get("characters", {}).get("edges", [])
        text = header + ("👥 **Characters:**\n\n" + "\n".join([f"▪️ **{c['node']['name']['full']}** ({c['role']})" for c in chars]) if chars else "❌ No character data.")

    text = text[:1024]
    kb = get_keyboard(media_id, tab, data.get("trailer"), data.get("siteUrl"))
    
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=text, reply_markup=kb)
        else:
            await query.edit_message_text(text=text, reply_markup=kb)
    except Exception:
        pass

#====================================================

