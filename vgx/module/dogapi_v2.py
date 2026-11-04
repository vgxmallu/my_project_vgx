import httpx
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode, ButtonStyle
from vgx import app
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from datetime import datetime, timedelta



BASE_URL = "https://dogapi.dog/api/v2/facts"

# --- API HELPER ---
async def fetch_dog_facts(limit: int = 1):
    """Fetches random dog fact(s) asynchronously from Dog API v2."""
    params = {"limit": limit}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(BASE_URL, params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            return [item["attributes"]["body"] for item in data.get("data", [])]
        except Exception as e:
            print(f"Dog Facts API Error: {e}")
            return []


# --- COMMAND HANDLERS ---

@app.on_message(filters.command(["dogfact", "fact"]))
async def cmd_single_dog_fact(client: Client, message: Message):
    """Command: /dogfact or /fact - Fetches 1 random dog fact."""
    facts = await fetch_dog_facts(limit=1)
    
    if not facts:
        return await message.reply_text("❌ Failed to fetch a dog fact. Please try again!")

    fact_text = f"🐶 **Did you know?**\n\n_{facts[0]}_"
    await message.reply_text(fact_text, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["dogfacts", "facts"]))
async def cmd_multiple_dog_facts(client: Client, message: Message):
    """Command: /dogfacts <count> - Fetches multiple dog facts (e.g., /dogfacts 3)."""
    args = message.command
    count = 3  # Default count if omitted
    
    if len(args) > 1 and args[1].isdigit():
        count = min(max(int(args[1]), 1), 5)  # Constrain between 1 and 5 facts for readability

    facts = await fetch_dog_facts(limit=count)
    
    if not facts:
        return await message.reply_text("❌ Failed to fetch dog facts. Please try again!")

    response_text = f"🐾 **Here are {len(facts)} Dog Facts:**\n\n"
    for idx, fact in enumerate(facts, 1):
        response_text += f"{idx}. _{fact}_\n\n"

    await message.reply_text(response_text, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("facthelp"))
async def cmd_fact_help(client: Client, message: Message):
    """Command: /facthelp - Displays command guide for dog facts."""
    help_text = (
        "📖 **Dog Facts Bot — Command Guide**\n\n"
        "• `/dogfact` or `/fact` — Get 1 random dog fact.\n"
        "• `/dogfacts <number>` — Get multiple facts (e.g., `/dogfacts 3`).\n"
        "• `/facthelp` — View this help guide.\n\n"
        "_Powered by Dog API v2 — No API key required!_"
    )
    await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)



db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["Dog_api_v2_db"]

# Base URL for Dog API v2
BASE_URL = "https://dogapi.dog/api/v2"

# In-memory session caches for pagination and active items
USER_DOG_SESSIONS = {}
BREED_CACHE = []
GROUP_CACHE = []

# --- MONGODB DATABASE HELPERS ---
async def add_favorite_dog_v2(user_id: int, breed_name: str, image_url: str):
    """Saves a dog image to user's favorites in MongoDB."""
    await db.dogv2_favorites.update_one(
        {"user_id": user_id, "image_url": image_url},
        {"$set": {"user_id": user_id, "breed_name": breed_name, "image_url": image_url}},
        upsert=True
    )

async def get_user_favorites_v2(user_id: int):
    """Retrieves saved favorite dogs for a user from MongoDB."""
    cursor = db.dogv2_favorites.find({"user_id": user_id}).sort("_id", -1).limit(10)
    return await cursor.to_list(length=None)

async def record_dog_vote_v2(user_id: int, image_url: str, vote_value: int):
    """Records a ❤️ (+1) or 💔 (-1) vote in MongoDB."""
    await db.dogv2_votes.update_one(
        {"user_id": user_id, "image_url": image_url},
        {"$set": {"vote": vote_value}},
        upsert=True
    )


# --- API HELPER ---
async def call_dog_api(endpoint: str, params: dict = None):
    """Fetches data from Dog API v2 asynchronously using httpx."""
    url = f"{BASE_URL}/{endpoint}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"DogAPI v2 Error [{endpoint}]: {e}")
            return None


async def get_cached_breeds():
    """Fetches and caches all dog breeds."""
    global BREED_CACHE
    if BREED_CACHE:
        return BREED_CACHE
    data = await call_dog_api("breeds", {"page[size]": 100})
    if data and "data" in data:
        BREED_CACHE = data["data"]
        return BREED_CACHE
    return []


# --- UI KEYBOARD BUILDERS ---
def get_main_dog_menu():
    """Main interactive hub for Dog API v2."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🐕 Random Dog Photo", callback_data="dv2_random", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("📚 Random Dog Facts", callback_data="dv2_facts", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🧬 Browse Breeds (280+)", callback_data="dv2_breed_0", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🐾 Browse Breed Groups", callback_data="dv2_group_0", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("⭐ My MongoDB Favourites", callback_data="dv2_fav_list", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("❌ Close", callback_data="dv2_close", style=ButtonStyle.DANGER)
        ]
    ])

def get_pagination_keyboard(index: int, total: int, mode: str):
    """Navigation control panel for list browsing."""
    prev_idx = max(0, index - 1)
    next_idx = min(total - 1, index + 1)
    prefix = f"dv2_{mode}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}_{prev_idx}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(f"📖 {index + 1} / {total}", callback_data="dv2_noop", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("Next ➡️", callback_data=f"{prefix}_{next_idx}", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🏠 Main Hub", callback_data="dv2_home", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("❌ Close", callback_data="dv2_close", style=ButtonStyle.DANGER)
        ]
    ])

def get_breed_action_keyboard(breed_id: str, image_url: str):
    """Actions for a specific breed photo."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Another Photo", callback_data=f"dv2_breedimg_{breed_id}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("⭐ Favourite", callback_data=f"dv2_fav_add", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("❤️ Like", callback_data="dv2_vote_1", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("💔 Dislike", callback_data="dv2_vote_-1", style=ButtonStyle.DANGER)
        ],
        [
            InlineKeyboardButton("🔙 Back to Breeds", callback_data="dv2_breed_0", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("❌ Close", callback_data="dv2_close", style=ButtonStyle.DANGER)
        ]
    ])


# --- COMMAND HANDLERS ---

@app.on_message(filters.command("dogv2"))
async def cmd_dogv2_hub(client: Client, message: Message):
    """Command: /dogv2 - Opens the Dog API v2 Central Control Hub."""
    text = (
        "🐕 **Dog API v2 — Control Center**\n\n"
        "Welcome! Explore 280+ dog breeds, 9 breed groups, 480+ facts, and high-res Wikimedia dog photos powered by **dogapi.dog**.\n\n"
        "👇 **Select a feature below to begin:**"
    )
    await message.reply_text(text, reply_markup=get_main_dog_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["dogfacts", "facts"]))
async def cmd_dog_facts(client: Client, message: Message):
    """Command: /dogfacts - Fetches random interesting dog facts."""
    data = await call_dog_api("facts", {"limit": 1})
    if not data or "data" not in data:
        return await message.reply_text("❌ Failed to fetch dog facts. Try again!")
    
    fact_text = data["data"][0]["attributes"]["body"]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Another Fact", callback_data="dv2_facts", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("🏠 Main Hub", callback_data="dv2_home", style=ButtonStyle.PRIMARY)]
    ])
    await message.reply_text(f"📚 **Did you know?**\n\n_{fact_text}_", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["dogbreeds", "breeds"]))
async def cmd_dog_breeds(client: Client, message: Message):
    """Command: /dogbreeds - Browses registered dog breeds."""
    await cb_breed_pagination(client, message, 0)


@app.on_message(filters.command("dogfavs"))
async def cmd_dog_favs(client: Client, message: Message):
    """Command: /dogfavs - Views user's saved favorite dogs from MongoDB."""
    user_id = message.from_user.id
    favs = await get_user_favorites_v2(user_id)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Hub", callback_data="dv2_home", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("❌ Close", callback_data="dv2_close", style=ButtonStyle.DANGER)]
    ])

    if not favs:
        text = "⭐ **Your Saved Favourites**\n\nNo favorite dogs saved yet! Browse breeds and click **⭐ Favourite** to store them."
        return await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    fav = favs[0]
    caption = f"⭐ **Saved Favourites (1 / {len(favs)})**\n🐾 Breed: `{fav.get('breed_name')}`\n_Stored securely in MongoDB_"
    
    try:
        await message.reply_photo(photo=fav["image_url"], caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await message.reply_text("⭐ Failed to load favorite photo.", reply_markup=kb)


# --- STRICT REGEX CALLBACK ROUTERS ---

@app.on_callback_query(filters.regex(r"^dv2_home$"))
async def cb_dv2_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🐕 **Dog API v2 — Control Center**\n\n"
        "Welcome! Explore 280+ dog breeds, 9 breed groups, 480+ facts, and high-res Wikimedia dog photos powered by **dogapi.dog**.\n\n"
        "👇 **Select a feature below to begin:**"
    )
    await query.message.edit_text(text, reply_markup=get_main_dog_menu(), parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^dv2_close$"))
async def cb_dv2_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()

@app.on_callback_query(filters.regex(r"^dv2_noop$"))
async def cb_dv2_noop(client: Client, query: CallbackQuery):
    await query.answer("📌 Current list position", show_alert=False)

@app.on_callback_query(filters.regex(r"^dv2_random$"))
async def cb_dv2_random(client: Client, query: CallbackQuery):
    await query.answer("Fetching a random dog...")
    # Dog API v2 random breed image redirect endpoint
    image_url = f"{BASE_URL}/breeds/image?size=medium&random=true"
    
    user_id = query.from_user.id
    USER_DOG_SESSIONS[user_id] = {"url": image_url, "breed": "Random Pup"}

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Another Random", callback_data="dv2_random", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("⭐ Favourite", callback_data="dv2_fav_add", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("❤️ Like", callback_data="dv2_vote_1", style=ButtonStyle.PRIMARY), InlineKeyboardButton("💔 Dislike", callback_data="dv2_vote_-1", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton("🏠 Main Hub", callback_data="dv2_home", style=ButtonStyle.PRIMARY)]
    ])

    try:
        await query.message.delete()
        await query.message.reply_photo(
            photo=image_url,
            caption="🐕 **Random Dog Photo**\n_Powered by Dog API v2_",
            reply_markup=kb,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await query.answer("❌ Error loading random dog image.", show_alert=True)

@app.on_callback_query(filters.regex(r"^dv2_facts$"))
async def cb_dv2_facts(client: Client, query: CallbackQuery):
    await query.answer("Fetching dog fact...")
    data = await call_dog_api("facts", {"limit": 1})
    if not data or "data" not in data:
        return await query.answer("❌ Failed to load fact.", show_alert=True)
    
    fact_text = data["data"][0]["attributes"]["body"]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Another Fact", callback_data="dv2_facts", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("🏠 Main Hub", callback_data="dv2_home", style=ButtonStyle.PRIMARY)]
    ])
    await query.message.edit_text(f"📚 **Did you know?**\n\n_{fact_text}_", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^dv2_breed_(?P<idx>\d+)$"))
async def cb_breed_pagination_cb(client: Client, query: CallbackQuery):
    idx = int(query.matches[0].group("idx"))
    await query.answer("Loading breeds list...")
    await show_breed_card(client, query.message, idx, is_callback=True)

async def show_breed_card(client, message, idx, is_callback=False):
    breeds = await get_cached_breeds()
    if not breeds:
        text = "❌ No breeds found."
        if is_callback:
            return await message.edit_text(text)
        return await message.reply_text(text)

    if idx >= len(breeds):
        idx = 0

    breed = breeds[idx]
    b_id = breed["id"]
    attr = breed["attributes"]
    name = attr.get("name", "Unknown")
    desc = attr.get("description", "No description available.")
    life = attr.get("life", {})
    life_span = f"{life.get('min', '?')} - {life.get('max', '?')} years"
    origin = attr.get("origin", {}).get("country", "Unknown") if attr.get("origin") else "Unknown"

    text = (
        f"🧬 **Breed Profile ({idx + 1}/{len(breeds)}): `{name}`**\n"
        f"🌍 **Origin:** `{origin}` | ⏳ **Lifespan:** `{life_span}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{desc[:350]}..."
    )

    # Store active session
    user_id = message.chat.id
    image_url = f"{BASE_URL}/breeds/{b_id}/image?size=medium&random=true"
    USER_DOG_SESSIONS[user_id] = {"url": image_url, "breed": name}

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ Prev", callback_data=f"dv2_breed_{max(0, idx - 1)}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(f"📖 {idx + 1}/{len(breeds)}", callback_data="dv2_noop", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("Next ➡️", callback_data=f"dv2_breed_{min(len(breeds)-1, idx + 1)}", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("📷 View Breed Photo", callback_data=f"dv2_breedimg_{b_id}", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🏠 Main Hub", callback_data="dv2_home", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("❌ Close", callback_data="dv2_close", style=ButtonStyle.DANGER)
        ]
    ])

    if is_callback:
        try:
            await message.delete()
            await message.reply_photo(photo=image_url, caption=text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply_photo(photo=image_url, caption=text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^dv2_breedimg_(?P<b_id>[a-zA-Z0-9_-]+)$"))
async def cb_breed_image(client: Client, query: CallbackQuery):
    b_id = query.matches[0].group("b_id")
    await query.answer("Fetching breed photo...")
    
    image_url = f"{BASE_URL}/breeds/{b_id}/image?size=medium&random=true"
    user_id = query.from_user.id
    USER_DOG_SESSIONS[user_id]["url"] = image_url

    kb = get_breed_action_keyboard(b_id, image_url)
    try:
        await query.message.delete()
        await query.message.reply_photo(photo=image_url, caption="🐾 **Breed Photo Gallery**", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await query.answer("❌ Failed to load image.", show_alert=True)

@app.on_callback_query(filters.regex(r"^dv2_group_(?P<idx>\d+)$"))
async def cb_groups(client: Client, query: CallbackQuery):
    global GROUP_CACHE
    idx = int(query.matches[0].group("idx"))
    
    if not GROUP_CACHE:
        data = await call_dog_api("groups")
        if data and "data" in data:
            GROUP_CACHE = data["data"]

    if not GROUP_CACHE:
        return await query.answer("❌ Failed to fetch breed groups.", show_alert=True)

    if idx >= len(GROUP_CACHE):
        idx = 0

    group = GROUP_CACHE[idx]
    name = group["attributes"]["name"]
    
    text = (
        f"🐾 **Breed Group ({idx + 1}/{len(GROUP_CACHE)}): `{name}`**\n\n"
        f"Classification group representing specific working traits and characteristics."
    )
    kb = get_pagination_keyboard(idx, len(GROUP_CACHE), mode="group")
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^dv2_fav_add$"))
async def cb_dv2_fav_add(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    session = USER_DOG_SESSIONS.get(user_id)
    
    if not session:
        return await query.answer("⚠️ Session expired. Please refresh!", show_alert=True)
    
    await add_favorite_dog_v2(user_id, session["breed"], session["url"])
    await query.answer("⭐ Added to your MongoDB Favourites!", show_alert=True)

@app.on_callback_query(filters.regex(r"^dv2_vote_(?P<val>1|-1)$"))
async def cb_dv2_vote(client: Client, query: CallbackQuery):
    vote_val = int(query.matches[0].group("val"))
    user_id = query.from_user.id
    session = USER_DOG_SESSIONS.get(user_id)
    
    if not session:
        return await query.answer("⚠️ Session expired.", show_alert=True)
    
    await record_dog_vote_v2(user_id, session["url"], vote_val)
    if vote_val == 1:
        await query.answer("❤️ Liked successfully in MongoDB!", show_alert=True)
    else:
        await query.answer("💔 Disliked recorded in MongoDB.", show_alert=True)

@app.on_callback_query(filters.regex(r"^dv2_fav_list$"))
async def cb_dv2_fav_list(client: Client, query: CallbackQuery):
    await query.answer("Loading your favourites...")
    user_id = query.from_user.id
    favs = await get_user_favorites_v2(user_id)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Hub", callback_data="dv2_home", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("❌ Close", callback_data="dv2_close", style=ButtonStyle.DANGER)]
    ])

    if not favs:
        text = "⭐ **Your Saved Favourites**\n\nNo favorite dogs saved yet! Browse breeds and click **⭐ Favourite**."
        return await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    fav = favs[0]
    caption = f"⭐ **Saved Favourites (1 / {len(favs)})**\n🐾 Breed: `{fav.get('breed_name')}`\n_Stored securely in MongoDB_"
    
    try:
        await query.message.delete()
        await query.message.reply_photo(photo=fav["image_url"], caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await query.message.edit_text("⭐ Failed to load favorite photo.", reply_markup=kb)
