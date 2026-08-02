import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton





class AniListClient:
    def __init__(self):
        self.url = "https://graphql.anilist.co"

    async def _post(self, query: str, variables: dict = None) -> dict:
        async with aiohttp.ClientSession() as session:
            payload = {"query": query, "variables": variables or {}}
            async with session.post(self.url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", {})
                return {}

    async def get_media(self, search: str, media_type: str = "ANIME") -> dict:
        query = """
        query ($search: String, $type: MediaType) {
          Media (search: $search, type: $type) {
            id
            title { romaji english native }
            type format status description(asHtml: false)
            startDate { year month day }
            endDate { year month day }
            season seasonYear episodes duration chapters volumes
            countryOfOrigin genres
            averageScore meanScore popularity trending
            coverImage { extraLarge }
            bannerImage
            siteUrl
            trailer { id site }
            studios { nodes { name } }
          }
        }
        """
        data = await self._post(query, {"search": search, "type": media_type})
        return data.get("Media", {})

    async def get_character(self, search: str) -> dict:
        query = """
        query ($search: String) {
          Character (search: $search) {
            id name { full native alternative }
            image { large }
            description(asHtml: false)
            gender dateOfBirth { year month day } age bloodType
            siteUrl
            media(page: 1, perPage: 3) {
              nodes { title { romaji } type }
            }
          }
        }
        """
        data = await self._post(query, {"search": search})
        return data.get("Character", {})

    async def get_staff(self, search: str) -> dict:
        query = """
        query ($search: String) {
          Staff (search: $search) {
            id name { full native }
            image { large }
            description(asHtml: false)
            primaryOccupations yearsActive
            siteUrl
          }
        }
        """
        data = await self._post(query, {"search": search})
        return data.get("Staff", {})

    async def get_studio(self, search: str) -> dict:
        query = """
        query ($search: String) {
          Studio (search: $search) {
            id name isAnimationStudio siteUrl
            media(page: 1, perPage: 5, sort: POPULARITY_DESC) {
              nodes { title { romaji } type format }
            }
          }
        }
        """
        data = await self._post(query, {"search": search})
        return data.get("Studio", {})

    async def get_user_profile(self, username: str) -> dict:
        query = """
        query ($name: String) {
          User (name: $name) {
            id name avatar { large } siteUrl
            statistics {
              anime { count meanScore minutesWatched episodesWatched }
              manga { count meanScore chaptersRead volumesRead }
            }
          }
        }
        """
        data = await self._post(query, {"name": username})
        return data.get("User", {})

    async def get_reviews_and_recs(self, search: str) -> dict:
        query = """
        query ($search: String) {
          Media (search: $search, type: ANIME) {
            title { romaji }
            reviews(perPage: 2) {
              nodes { summary rating score user { name } }
            }
            recommendations(perPage: 3) {
              nodes { mediaRecommendation { title { romaji } } }
            }
          }
        }
        """
        data = await self._post(query, {"search": search})
        return data.get("Media", {})

    async def get_airing_schedule() -> list:
        query = """
        query {
          Page(page: 1, perPage: 5) {
            airingSchedules(notYetAiring: true, sort: TIME) {
              airingAt timeUntilAiring episode
              media { title { romaji } siteUrl }
            }
          }
        }
        """
        data = await self._post(query)
        return data.get("Page", {}).get("airingSchedules", [])

    async def get_trending_anime() -> list:
        query = """
        query {
          Page(page: 1, perPage: 5) {
            media(type: ANIME, sort: TRENDING_DESC) {
              title { romaji } averageScore format episodes siteUrl
            }
          }
        }
        """
        data = await self._post(query)
        return data.get("Page", {}).get("media", [])

anilist = AniListClient()



def media_keyboard(url: str, trailer: dict = None) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton("🌐 View on AniList", url=url)]]
    if trailer and trailer.get("site") == "youtube":
        yt_url = f"https://www.youtube.com/watch?v={trailer.get('id')}"
        buttons.append([InlineKeyboardButton("🎬 Watch Trailer", url=yt_url)])
    return InlineKeyboardMarkup(buttons)

def link_keyboard(label: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(f"🔗 {label}", url=url)]])


@Client.on_message(filters.command("anime"))
async def cmd_anime(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/anime <title></code>")
    
    query = " ".join(message.command[1:])
    msg = await message.reply_text("🔎 Searching AniList Anime Database...")
    data = await anilist.get_media(query, "ANIME")
    
    if not data:
        return await msg.edit_text("❌ Anime not found.")

    title = data.get("title", {}).get("romaji", "N/A")
    eng_title = data.get("title", {}).get("english", "")
    score = data.get("averageScore", "N/A")
    episodes = data.get("episodes", "N/A")
    status = data.get("status", "N/A")
    genres = ", ".join(data.get("genres", []))
    desc = data.get("description", "No description available.")[:250] + "..."
    
    text = (
        f"📺 <b>{title}</b> ({eng_title})\n\n"
        f"<b>Format:</b> {data.get('format', 'N/A')} | <b>Status:</b> {status}\n"
        f"<b>Episodes:</b> {episodes} | <b>Score:</b> {score}%\n"
        f"<b>Genres:</b> {genres}\n\n"
        f"📖 <i>{desc}</i>"
    )
    
    cover = data.get("coverImage", {}).get("extraLarge")
    kb = media_keyboard(data.get("siteUrl", "https://anilist.co"), data.get("trailer"))
    
    await msg.delete()
    if cover:
        await message.reply_photo(cover, caption=text, reply_markup=kb)
    else:
        await message.reply_text(text, reply_markup=kb)

@Client.on_message(filters.command("manga"))
async def cmd_manga(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/manga <title></code>")
    
    query = " ".join(message.command[1:])
    msg = await message.reply_text("🔎 Searching AniList Manga Database...")
    data = await anilist.get_media(query, "MANGA")
    
    if not data:
        return await msg.edit_text("❌ Manga not found.")

    title = data.get("title", {}).get("romaji", "N/A")
    chapters = data.get("chapters", "N/A")
    volumes = data.get("volumes", "N/A")
    score = data.get("averageScore", "N/A")
    
    text = (
        f"📖 <b>{title}</b>\n\n"
        f"<b>Format:</b> {data.get('format', 'N/A')} | <b>Status:</b> {data.get('status', 'N/A')}\n"
        f"<b>Chapters:</b> {chapters} | <b>Volumes:</b> {volumes}\n"
        f"<b>Score:</b> {score}%\n"
        f"<b>Genres:</b> {', '.join(data.get('genres', []))}\n"
    )
    
    cover = data.get("coverImage", {}).get("extraLarge")
    kb = media_keyboard(data.get("siteUrl", "https://anilist.co"))
    
    await msg.delete()
    if cover:
        await message.reply_photo(cover, caption=text, reply_markup=kb)
    else:
        await message.reply_text(text, reply_markup=kb)


@Client.on_message(filters.command("character"))
async def cmd_character(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/character <name></code>")
    
    query = " ".join(message.command[1:])
    data = await anilist.get_character(query)
    
    if not data:
        return await message.reply_text("❌ Character not found.")

    name = data.get("name", {}).get("full", "N/A")
    native = data.get("name", {}).get("native", "")
    gender = data.get("gender", "N/A")
    age = data.get("age", "N/A")
    
    text = (
        f"👤 <b>{name}</b> ({native})\n\n"
        f"<b>Gender:</b> {gender} | <b>Age:</b> {age}\n"
        f"<b>Blood Type:</b> {data.get('bloodType', 'N/A')}\n"
    )
    
    image = data.get("image", {}).get("large")
    kb = link_keyboard("View Character", data.get("siteUrl", "https://anilist.co"))
    
    if image:
        await message.reply_photo(image, caption=text, reply_markup=kb)
    else:
        await message.reply_text(text, reply_markup=kb)

@Client.on_message(filters.command("staff"))
async def cmd_staff(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/staff <name></code>")
    
    query = " ".join(message.command[1:])
    data = await anilist.get_staff(query)
    
    if not data:
        return await message.reply_text("❌ Staff member not found.")

    name = data.get("name", {}).get("full", "N/A")
    occupations = ", ".join(data.get("primaryOccupations", []))
    
    text = (
        f"🎨 <b>{name}</b>\n\n"
        f"<b>Primary Occupations:</b> {occupations or 'N/A'}\n"
    )
    
    image = data.get("image", {}).get("large")
    kb = link_keyboard("View Staff Profile", data.get("siteUrl", "https://anilist.co"))
    
    if image:
        await message.reply_photo(image, caption=text, reply_markup=kb)
    else:
        await message.reply_text(text, reply_markup=kb)

@Client.on_message(filters.command("studio"))
async def cmd_studio(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/studio <name></code>")
    
    query = " ".join(message.command[1:])
    data = await anilist.get_studio(query)
    
    if not data:
        return await message.reply_text("❌ Studio not found.")

    name = data.get("name", "N/A")
    media_list = data.get("media", {}).get("nodes", [])
    
    text = f"🏢 <b>Studio: {name}</b>\n\n<b>Top Popular Works:</b>\n"
    for item in media_list:
        text += f"▪️ {item.get('title', {}).get('romaji')} ({item.get('format')})\n"
        
    kb = link_keyboard("View Studio", data.get("siteUrl", "https://anilist.co"))
    await message.reply_text(text, reply_markup=kb)


@Client.on_message(filters.command("user"))
async def cmd_user(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/user <username></code>")
    
    username = message.command[1]
    data = await anilist.get_user_profile(username)
    
    if not data:
        return await message.reply_text("❌ User profile not found.")

    stats = data.get("statistics", {})
    anime_stats = stats.get("anime", {})
    manga_stats = stats.get("manga", {})
    
    text = (
        f"📊 <b>AniList User Profile: {data.get('name')}</b>\n\n"
        f"<b>📺 Anime Stats:</b>\n"
        f"▪️ Count: {anime_stats.get('count', 0)} | Mean Score: {anime_stats.get('meanScore', 0)}\n"
        f"▪️ Episodes Watched: {anime_stats.get('episodesWatched', 0)}\n\n"
        f"<b>📖 Manga Stats:</b>\n"
        f"▪️ Count: {manga_stats.get('count', 0)} | Mean Score: {manga_stats.get('meanScore', 0)}\n"
        f"▪️ Chapters Read: {manga_stats.get('chaptersRead', 0)}"
    )
    
    avatar = data.get("avatar", {}).get("large")
    kb = link_keyboard("View Full Profile", data.get("siteUrl", "https://anilist.co"))
    
    if avatar:
        await message.reply_photo(avatar, caption=text, reply_markup=kb)
    else:
        await message.reply_text(text, reply_markup=kb)

@Client.on_message(filters.command("reviews"))
async def cmd_reviews(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/reviews <anime_title></code>")
    
    query = " ".join(message.command[1:])
    data = await anilist.get_reviews_and_recs(query)
    
    if not data:
        return await message.reply_text("❌ Media not found for reviews.")

    title = data.get("title", {}).get("romaji", "")
    reviews = data.get("reviews", {}).get("nodes", [])
    recs = data.get("recommendations", {}).get("nodes", [])
    
    text = f"📝 <b>Reviews & Recommendations for {title}</b>\n\n<b>Reviews:</b>\n"
    for rev in reviews:
        text += f"▪️ <i>\"{rev.get('summary')}\"</i> - {rev.get('user', {}).get('name')} ({rev.get('score')}/100)\n"
        
    text += "\n<b>Recommendations:</b>\n"
    for rec in recs:
        rec_title = rec.get("mediaRecommendation", {}).get("title", {}).get("romaji")
        if rec_title:
            text += f"▪️ {rec_title}\n"
            
    await message.reply_text(text)

@Client.on_message(filters.command("airing"))
async def cmd_airing(client: Client, message: Message):
    schedules = await anilist.get_airing_schedule()
    
    if not schedules:
        return await message.reply_text("❌ Unable to fetch current airing schedule.")

    text = "📡 <b>Upcoming Episode Airing Schedule</b>\n\n"
    for item in schedules:
        title = item.get("media", {}).get("title", {}).get("romaji")
        ep = item.get("episode")
        seconds = item.get("timeUntilAiring", 0)
        hours = seconds // 3600
        
        text += f"▪️ <b>{title}</b> - Ep {ep} in ~{hours}h\n"
        
    await message.reply_text(text)

@Client.on_message(filters.command("trending"))
async def cmd_trending(client: Client, message: Message):
    media = await anilist.get_trending_anime()
    
    if not media:
        return await message.reply_text("❌ Unable to fetch trending anime.")

    text = "🔥 <b>Top Trending Anime Right Now</b>\n\n"
    for idx, item in enumerate(media, start=1):
        title = item.get("title", {}).get("romaji")
        score = item.get("averageScore", "N/A")
        fmt = item.get("format", "N/A")
        
        text += f"<b>{idx}. {title}</b> ({fmt}) - {score}%\n"
        
    await message.reply_text(text)
