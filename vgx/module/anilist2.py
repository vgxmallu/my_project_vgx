from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message



class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGO_URL)
        self.db = self.client["anilist_bot_db"]
        self.users = self.db["users"]

    async def save_token(self, user_id: int, access_token: str):
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"access_token": access_token}},
            upsert=True
        )

    async def get_token(self, user_id: int) -> str:
        user = await self.users.find_one({"user_id": user_id})
        return user.get("access_token") if user else None

db = Database()


class AniListAPI:
    async def exchange_auth_code(self, authorization_code: str) -> str:
        """Exchanges the PIN/Code for an OAuth2 Access Token using Client ID/Secret."""
        payload = {
            "grant_type": "authorization_code",
            "client_id": Config.ANILIST_CLIENT_ID,
            "client_secret": Config.ANILIST_CLIENT_SECRET,
            "redirect_uri": "https://anilist.co/api/v2/oauth/pin",
            "code": authorization_code
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(Config.OAUTH_URL, json=payload) as resp:
                data = await resp.json()
                return data.get("access_token")

    async def _request(self, query: str, variables: dict = None, user_id: int = None) -> dict:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        
        if user_id:
            token = await db.get_token(user_id)
            if token:
                headers["Authorization"] = f"Bearer {token}"

        async with aiohttp.ClientSession() as session:
            payload = {"query": query, "variables": variables or {}}
            async with session.post(Config.GRAPHQL_URL, json=payload, headers=headers) as resp:
                data = await resp.json()
                return data.get("data", {})

    # --- 1. Media Data ---
    async def get_media(self, search: str, m_type: str = "ANIME") -> dict:
        query = """
        query ($search: String, $type: MediaType) {
          Media (search: $search, type: $type) {
            id title { romaji english native } type format status
            startDate { year month day } endDate { year month day }
            season episodes chapters volumes countryOfOrigin genres tags { name description }
            averageScore meanScore popularity trending
            coverImage { extraLarge } bannerImage siteUrl trailer { site id }
          }
        }
        """
        data = await self._request(query, {"search": search, "type": m_type})
        return data.get("Media", {})

    # --- 2. Characters & Staff ---
    async def get_character(self, search: str) -> dict:
        query = """
        query ($search: String) {
          Character (search: $search) {
            name { full native } image { large } gender age bloodType dateOfBirth { year month day }
          }
        }
        """
        data = await self._request(query, {"search": search})
        return data.get("Character", {})

    async def get_staff(self, search: str) -> dict:
        query = """
        query ($search: String) {
          Staff (search: $search) {
            name { full native } image { large } primaryOccupations yearsActive
          }
        }
        """
        data = await self._request(query, {"search": search})
        return data.get("Staff", {})

    # --- 3. User & Social Data ---
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

    # --- 4. Live Airing Data ---
    async def get_schedules(self) -> list:
        query = """
        query {
          Page(page: 1, perPage: 5) {
            airingSchedules(notYetAiring: true, sort: TIME) {
              episode timeUntilAiring media { title { romaji } }
            }
          }
        }
        """
        data = await self._request(query)
        return data.get("Page", {}).get("airingSchedules", [])

    # --- Authenticated Mutations ---
    async def update_list(self, user_id: int, media_id: int, progress: int) -> dict:
        mutation = """
        mutation ($mediaId: Int, $progress: Int) {
          SaveMediaListEntry (mediaId: $mediaId, progress: $progress) {
            mediaId progress status media { title { romaji } }
          }
        }
        """
        data = await self._request(mutation, {"mediaId": media_id, "progress": progress}, user_id)
        return data.get("SaveMediaListEntry", {})

api = AniListAPI()


@Client.on_message(filters.command("login"))
async def cmd_login(client: Client, message: Message):
    auth_url = f"https://anilist.co/api/v2/oauth/authorize?client_id={Config.ANILIST_CLIENT_ID}&redirect_uri=https://anilist.co/api/v2/oauth/pin&response_type=code"
    text = (
        "🔐 **Connect your AniList Account**\n\n"
        f"1. [Click here to Authorize]({auth_url})\n"
        "2. Copy the PIN code provided.\n"
        "3. Send it to me using: `/auth YOUR_PIN`"
    )
    await message.reply_text(text, disable_web_page_preview=True)

@Client.on_message(filters.command("auth"))
async def cmd_auth(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Provide your PIN: `/auth PIN`")
    
    pin = message.command[1]
    msg = await message.reply_text("🔄 Verifying code...")
    
    token = await api.exchange_auth_code(pin)
    if token:
        await db.save_token(message.from_user.id, token)
        await msg.edit_text("✅ **Successfully linked your AniList account!** You can now use personalized commands.")
    else:
        await msg.edit_text("❌ Invalid or expired PIN. Please generate a new one using `/login`.")


@Client.on_message(filters.command("anime"))
async def cmd_anime(client: Client, message: Message):
    if len(message.command) < 2: return await message.reply_text("Usage: `/anime title`")
    
    data = await api.get_media(" ".join(message.command[1:]), "ANIME")
    if not data: return await message.reply_text("❌ Not found.")

    title = data.get('title', {}).get('romaji', 'Unknown')
    text = (
        f"📺 **{title}**\n"
        f"▪️ **Format:** {data.get('format')} | **Status:** {data.get('status')}\n"
        f"▪️ **Eps:** {data.get('episodes')} | **Score:** {data.get('averageScore')}%\n"
        f"▪️ **Genres:** {', '.join(data.get('genres', []))}\n"
        f"🔗 [View on AniList]({data.get('siteUrl')})"
    )
    
    img = data.get('coverImage', {}).get('extraLarge')
    if img: await message.reply_photo(img, caption=text)
    else: await message.reply_text(text)

@Client.on_message(filters.command("setprogress"))
async def cmd_setprogress(client: Client, message: Message):
    """Requires Authentication via /login"""
    if len(message.command) < 3: return await message.reply_text("Usage: `/setprogress anime_id episodes`")
    
    media_id, progress = int(message.command[1]), int(message.command[2])
    data = await api.update_list(message.from_user.id, media_id, progress)
    
    if not data:
        return await message.reply_text("❌ Failed. Have you linked your account with `/login`?")
        
    title = data.get('media', {}).get('title', {}).get('romaji')
    await message.reply_text(f"✅ Updated **{title}** to Episode **{data.get('progress')}**!")

@Client.on_message(filters.command("character"))
async def cmd_character(client: Client, message: Message):
    if len(message.command) < 2: return await message.reply_text("Usage: `/character name`")
    
    data = await api.get_character(" ".join(message.command[1:]))
    if not data: return await message.reply_text("❌ Not found.")

    name = data.get('name', {}).get('full', 'Unknown')
    text = f"👤 **{name}**\n▪️ **Gender:** {data.get('gender')}\n▪️ **Age:** {data.get('age')}"
    
    img = data.get('image', {}).get('large')
    if img: await message.reply_photo(img, caption=text)
    else: await message.reply_text(text)

@Client.on_message(filters.command("airing"))
async def cmd_airing(client: Client, message: Message):
    schedules = await api.get_schedules()
    if not schedules: return await message.reply_text("❌ No data.")

    text = "📡 **Upcoming Episodes**\n\n"
    for item in schedules:
        title = item.get('media', {}).get('title', {}).get('romaji')
        hours = item.get('timeUntilAiring', 0) // 3600
        text += f"▪️ **{title}** (Ep {item.get('episode')}) - in {hours}h\n"
        
    await message.reply_text(text)
