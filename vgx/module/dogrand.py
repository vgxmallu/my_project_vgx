import httpx
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode, ButtonStyle
from vgx import app
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from datetime import datetime, timedelta

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["Dog_random"]



# In-memory session cache to handle voting/favoriting on active user photos
USER_DOG_SESSIONS = {}

# --- MONGODB DATABASE HELPERS ---
async def add_favorite_dog(user_id: int, image_url: str):
    """Saves a dog image to user's favorites in MongoDB."""
    await db.dog_favorites.update_one(
        {"user_id": user_id, "image_url": image_url},
        {"$set": {"user_id": user_id, "image_url": image_url}},
        upsert=True
    )

async def get_user_favorites(user_id: int):
    """Retrieves all saved favorite dog URLs for a user from MongoDB."""
    cursor = db.dog_favorites.find({"user_id": user_id}).sort("_id", -1).limit(10)
    return await cursor.to_list(length=None)

async def record_dog_vote(user_id: int, image_url: str, vote_value: int):
    """Records a ❤️ (+1) or 💔 (-1) vote for a specific dog image in MongoDB."""
    await db.dog_votes.update_one(
        {"user_id": user_id, "image_url": image_url},
        {"$set": {"vote": vote_value}},
        upsert=True
    )


# --- API HELPER ---
async def fetch_random_dog():
    """Fetches a random dog image URL from Dog CEO API."""
    url = "https://dog.ceo/api/breeds/image/random"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return data.get("message")
        except Exception as e:
            print(f"Dog API Error: {e}")
        return None


# --- UI KEYBOARD BUILDERS ---
def get_dog_action_keyboard():
    """Interactive control panel using clean callback data."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Another Dog", callback_data="dog_random", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("⭐ Favourite", callback_data="dog_fav_add", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("❤️ Like", callback_data="dog_vote_1", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("💔 Dislike", callback_data="dog_vote_-1", style=ButtonStyle.DANGER)
        ],
        [
            InlineKeyboardButton("📂 My Favourites", callback_data="dog_fav_list", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("❌ Close", callback_data="dog_close", style=ButtonStyle.DANGER)
        ]
    ])

def get_main_dog_menu():
    """Main Hub Menu."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🐕 Explore Random Dogs", callback_data="dog_random", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("⭐ My Saved Favourites", callback_data="dog_fav_list", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("📖 Help & Info", callback_data="dog_help", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("❌ Close", callback_data="dog_close", style=ButtonStyle.DANGER)
        ]
    ])


# --- COMMAND HANDLERS ---

@app.on_message(filters.command("dogs"))
async def cmd_dogs_hub(client: Client, message: Message):
    """Command: /dogs - Opens the Dog CEO Control Center Hub."""
    welcome_text = (
        "🐶 **Dog CEO - Canine Hub**\n\n"
        "Welcome! Explore endless random dog photos, vote with ❤️ and 💔, and save your favorite pups to MongoDB.\n\n"
        "👇 **Select an option below to begin:**"
    )
    await message.reply_text(welcome_text, reply_markup=get_main_dog_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("randomdog"))
async def cmd_random_dog(client: Client, message: Message):
    """Command: /dog or /randomdog - Instantly fetches a random dog photo."""
    msg = await message.reply_text("Fetching a random dog...")
    image_url = await fetch_random_dog()
    
    if not image_url:
        return await msg.edit_text("❌ Failed to fetch dog image. Please try again!")

    user_id = message.from_user.id
    USER_DOG_SESSIONS[user_id] = image_url

    caption = (
        "🐕 **Random Dog Photo**\n"
        "_Powered by Dog CEO API_\n\n"
        "• Use **❤️** or **💔** to vote!\n"
        "• Click **⭐ Favourite** to save to MongoDB."
    )
    
    try:
        await msg.delete()
        await message.reply_photo(
            photo=image_url,
            caption=caption,
            reply_markup=get_dog_action_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await message.reply_text(f"❌ Error sending photo: {str(e)}")


@app.on_message(filters.command(["dogfavs", "dogfavorites"]))
async def cmd_dog_favs(client: Client, message: Message):
    """Command: /dogfavs - Displays saved favorite dog photos from MongoDB."""
    user_id = message.from_user.id
    favs = await get_user_favorites(user_id)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Browse Live Dogs", callback_data="dog_random", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("🏠 Main Hub", callback_data="dog_home", style=ButtonStyle.PRIMARY), InlineKeyboardButton("❌ Close", callback_data="dog_close", style=ButtonStyle.DANGER)]
    ])

    if not favs:
        text = "⭐ **Your Saved Favourites**\n\nNo dogs saved yet! Use `/dog` and click **⭐ Favourite** to save photos to MongoDB."
        return await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    fav = favs[0]
    caption = f"⭐ **Your Saved Favourites (1 / {len(favs)})**\n_Stored securely in MongoDB_"
    
    try:
        await message.reply_photo(photo=fav["image_url"], caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await message.reply_text("⭐ Failed to load favorite photo from database.", reply_markup=kb)


@app.on_message(filters.command("doghelp"))
async def cmd_dog_help(client: Client, message: Message):
    """Command: /doghelp - Displays command documentation."""
    text = (
        "📖 **Dog CEO Bot - Command Guide**\n\n"
        "• `/dogs` — Opens the main Canine Hub dashboard.\n"
        "• `/dog` or `/randomdog` — Fetch a random dog photo.\n"
        "• `/dogfavs` — View your saved favorite dogs from MongoDB.\n"
        "• `/doghelp` — View this help menu.\n\n"
        "**Interactive Controls:**\n"
        "• **❤️ Like / 💔 Dislike:** Save your ratings directly to MongoDB.\n"
        "• **⭐ Favourite:** Bookmarks photos to your personal list."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Hub", callback_data="dog_home", style=ButtonStyle.PRIMARY)]])
    await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# --- STRICT REGEX CALLBACK ROUTERS ---

@app.on_callback_query(filters.regex(r"^dog_home$"))
async def cb_dog_home(client: Client, query: CallbackQuery):
    await query.answer()
    welcome_text = (
        "🐶 **Dog CEO - Canine Hub**\n\n"
        "Welcome! Explore endless random dog photos, vote with ❤️ and 💔, and save your favorite pups to MongoDB.\n\n"
        "👇 **Select an option below to begin:**"
    )
    await query.message.edit_text(welcome_text, reply_markup=get_main_dog_menu(), parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^dog_close$"))
async def cb_dog_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()

@app.on_callback_query(filters.regex(r"^dog_random$"))
async def cb_dog_random(client: Client, query: CallbackQuery):
    await query.answer("Fetching a random dog...")
    image_url = await fetch_random_dog()
    
    if not image_url:
        return await query.answer("❌ Failed to fetch dog image. Try again!", show_alert=True)

    user_id = query.from_user.id
    USER_DOG_SESSIONS[user_id] = image_url

    caption = (
        "🐕 **Random Dog Photo**\n"
        "_Powered by Dog CEO API_\n\n"
        "• Use **❤️** or **💔** to vote!\n"
        "• Click **⭐ Favourite** to save to MongoDB."
    )
    
    try:
        await query.message.delete()
        await query.message.reply_photo(
            photo=image_url,
            caption=caption,
            reply_markup=get_dog_action_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await query.answer(f"❌ Error sending image: {str(e)}", show_alert=True)

@app.on_callback_query(filters.regex(r"^dog_fav_add$"))
async def cb_dog_fav_add(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    image_url = USER_DOG_SESSIONS.get(user_id)
    
    if not image_url:
        return await query.answer("⚠️ Session expired. Click 'Another Dog' to refresh!", show_alert=True)
    
    await add_favorite_dog(user_id, image_url)
    await query.answer("⭐ Added to your MongoDB Favourites!", show_alert=True)

@app.on_callback_query(filters.regex(r"^dog_vote_(?P<val>1|-1)$"))
async def cb_dog_vote(client: Client, query: CallbackQuery):
    vote_val = int(query.matches[0].group("val"))
    user_id = query.from_user.id
    image_url = USER_DOG_SESSIONS.get(user_id)
    
    if not image_url:
        return await query.answer("⚠️ Session expired. Click 'Another Dog' to refresh!", show_alert=True)
    
    await record_dog_vote(user_id, image_url, vote_val)
    if vote_val == 1:
        await query.answer("❤️ You liked this dog!", show_alert=True)
    else:
        await query.answer("💔 You disliked this dog.", show_alert=True)

@app.on_callback_query(filters.regex(r"^dog_fav_list$"))
async def cb_dog_fav_list(client: Client, query: CallbackQuery):
    await query.answer("Loading your favourites...")
    user_id = query.from_user.id
    favs = await get_user_favorites(user_id)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Browse Live Dogs", callback_data="dog_random", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("🏠 Main Hub", callback_data="dog_home", style=ButtonStyle.PRIMARY), InlineKeyboardButton("❌ Close", callback_data="dog_close", style=ButtonStyle.DANGER)]
    ])

    if not favs:
        text = "⭐ **Your Saved Favourites**\n\nNo dogs saved yet! Browse random dogs using `/dog` and click **⭐ Favourite** to store them in MongoDB."
        return await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    fav = favs[0]
    caption = f"⭐ **Your Saved Favourites (1 / {len(favs)})**\n_Stored securely in MongoDB_"
    
    try:
        await query.message.delete()
        await query.message.reply_photo(photo=fav["image_url"], caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await query.message.edit_text("⭐ Failed to load favorite photo.", reply_markup=kb)

@app.on_callback_query(filters.regex(r"^dog_help$"))
async def cb_dog_help(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "📖 **Dog CEO Bot - Command Guide**\n\n"
        "• `/dogs` — Opens the main Canine Hub dashboard.\n"
        "• `/dog` or `/randomdog` — Fetch a random dog photo.\n"
        "• `/dogfavs` — View your saved favorite dogs from MongoDB.\n"
        "• `/doghelp` — View this help menu.\n\n"
        "**Interactive Controls:**\n"
        "• **❤️ Like / 💔 Dislike:** Save your ratings directly to MongoDB.\n"
        "• **⭐ Favourite:** Bookmarks photos to your personal list."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Hub", callback_data="dog_home", style=ButtonStyle.PRIMARY)]])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
