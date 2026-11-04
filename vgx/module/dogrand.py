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
# --- MONGODB DATABASE HELPERS ---
async def add_favorite_dog(user_id: int, image_url: str):
    """Saves a dog image to user's favorites in MongoDB."""
    await db.dog_favorites.update_one(
        {"user_id": user_id, "image_url": image_url},
        {"$set": {"user_id": user_id, "image_url": image_url}},
        upsert=True
    )

async def get_user_favorites(user_id: int):
    """Retrieves all saved favorite dog URLs for a user."""
    cursor = db.dog_favorites.find({"user_id": user_id}).sort("_id", -1).limit(10)
    return await cursor.to_list(length=None)

async def record_dog_vote(user_id: int, image_url: str, vote_value: int):
    """Records a ❤️ (+1) or 💔 (-1) vote for a specific dog image."""
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
def get_dog_action_keyboard(image_url: str):
    """Interactive control panel for random dogs with ❤️ and 💔 votes."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Another Dog", callback_data="dog_random", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("⭐ Favourite", callback_data=f"dog_fav_add_{image_url}", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("❤️ Like", callback_data=f"dog_vote_{image_url}_1", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("💔 Dislike", callback_data=f"dog_vote_{image_url}_-1", style=ButtonStyle.DANGER)
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
async def dogs_command(client: Client, message: Message):
    """Command: /dogs - Opens the Dog CEO Control Center."""
    welcome_text = (
        "🐶 **Dog CEO - Canine Hub**\n\n"
        "Welcome! Explore endless random dog photos, vote with ❤️ and 💔, and save your favorite pups to MongoDB.\n\n"
        "👇 **Select an option below to begin:**"
    )
    await message.reply_text(welcome_text, reply_markup=get_main_dog_menu(), parse_mode=ParseMode.MARKDOWN)


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
            reply_markup=get_dog_action_keyboard(image_url),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await query.answer("❌ Error sending image.", show_alert=True)

@app.on_callback_query(filters.regex(r"^dog_fav_add_(?P<url>.+)$"))
async def cb_dog_fav_add(client: Client, query: CallbackQuery):
    image_url = query.matches[0].group("url")
    user_id = query.from_user.id
    
    await add_favorite_dog(user_id, image_url)
    await query.answer("⭐ Added to your MongoDB Favourites!", show_alert=True)

@app.on_callback_query(filters.regex(r"^dog_vote_(?P<url>.+)_(?P<val>1|-1)$"))
async def cb_dog_vote(client: Client, query: CallbackQuery):
    image_url = query.matches[0].group("url")
    vote_val = int(query.matches[0].group("val"))
    user_id = query.from_user.id
    
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
    
    if not favs:
        text = "⭐ **Your Saved Favourites**\n\nNo dogs saved yet! Browse random dogs and click **⭐ Favourite** to store them."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Hub", callback_data="dog_home", style=ButtonStyle.PRIMARY)]])
        return await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # Send the first saved favorite or a summary menu
    fav = favs[0]
    caption = f"⭐ **Your Saved Favourites (1 / {len(favs)})**\n_Stored securely in MongoDB_"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Browse Live Dogs", callback_data="dog_random", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("🏠 Main Hub", callback_data="dog_home", style=ButtonStyle.PRIMARY), InlineKeyboardButton("❌ Close", callback_data="dog_close", style=ButtonStyle.DANGER)]
    ])
    
    try:
        await query.message.delete()
        await query.message.reply_photo(photo=fav["image_url"], caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await query.message.edit_text("⭐ Failed to load favorite photo.", reply_markup=kb)

@app.on_callback_query(filters.regex(r"^dog_help$"))
async def cb_dog_help(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "📖 **Dog CEO Bot - Help Center**\n\n"
        "• `/dogs` — Opens the main Canine Hub.\n"
        "• **Voting (`❤️` / `💔`):** Records your likes and dislikes in MongoDB.\n"
        "• **Favorites (`⭐`):** Bookmarks your favorite puppy photos to your personal profile."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Hub", callback_data="dog_home", style=ButtonStyle.PRIMARY)]])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
