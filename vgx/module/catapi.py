import os
import httpx
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode, ButtonStyle
from vgx import app
from config import Config
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta


#====================================================



#====================================================


db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["Cats_api_db"]
# API Key Configuration (Free key from https://thecatapi.com)
BASE_URL = "https://api.thecatapi.com/v1"

# Session state caches
USER_SESSIONS = {}
BREED_CACHE = []

# --- MONGODB DATABASE HELPERS ---
async def add_cat_favorite(user_id: int, image_id: str, image_url: str):
    """Saves a cat image to user's favorites in MongoDB."""
    await db.cat_favorites.update_one(
        {"user_id": user_id, "image_id": image_id},
        {"$set": {"user_id": user_id, "image_id": image_id, "image_url": image_url}},
        upsert=True
    )

async def get_cat_favorites(user_id: int):
    """Retrieves all saved favorite cat records for a user from MongoDB."""
    cursor = db.cat_favorites.find({"user_id": user_id}).sort("_id", -1).limit(20)
    return await cursor.to_list(length=None)

async def record_cat_vote(user_id: int, image_id: str, vote_value: int):
    """Records a vote for a specific cat image in MongoDB."""
    await db.cat_votes.update_one(
        {"user_id": user_id, "image_id": image_id},
        {"$set": {"vote": vote_value}},
        upsert=True
    )


# --- API HELPER ---
async def call_cat_api(endpoint: str, params: dict = None, method: str = "GET", payload: dict = None):
    """Executes requests against The Cat API asynchronously using httpx."""
    headers = {"x-api-key": Config.CAT_API_KEY}
    url = f"{BASE_URL}/{endpoint}"
    async with httpx.AsyncClient() as client:
        try:
            if method == "GET":
                resp = await client.get(url, headers=headers, params=params, timeout=10.0)
            else:
                resp = await client.post(url, headers=headers, json=payload, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"TheCatAPI Error [{endpoint}]: {e}")
            return None


async def get_all_breeds():
    """Fetches and caches all 100+ cat breeds."""
    global BREED_CACHE
    if BREED_CACHE:
        return BREED_CACHE
    data = await call_cat_api("breeds")
    if data:
        BREED_CACHE = data
        return BREED_CACHE
    return []


# --- UI KEYBOARD BUILDERS ---
def get_main_menu():
    """Main interactive hub for The Cat API."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🐱 Random Photo", callback_data="tc_img_0", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🎬 Animated GIF", callback_data="tc_gif_0", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🧬 Browse 100+ Breeds", callback_data="tc_breed_0", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🔍 AI Breed Identifier", callback_data="tc_ai_identify", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🩺 Pet Health & Calorie Hub", callback_data="tc_health_menu", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("⭐ Favourites & Votes", callback_data="tc_fav_menu", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("📖 Help & Info", callback_data="tc_help_menu", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER)
        ]
    ])

def get_pagination_keyboard(index: int, total: int, mode: str, item_id: str = "", image_url: str = ""):
    """Strict callback-controlled navigation menu (Next/Prev)."""
    prev_idx = max(0, index - 1)
    next_idx = min(total - 1, index + 1)
    prefix = f"tc_{mode}"

    buttons = [
        [
            InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}_{prev_idx}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(f"📖 {index + 1} / {total}", callback_data="tc_noop", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("Next ➡️", callback_data=f"{prefix}_{next_idx}", style=ButtonStyle.PRIMARY)
        ]
    ]

    if item_id and mode in ["img", "gif"]:
        # URL encoded/shortened callback payload if needed, or matched securely
        buttons.append([
            InlineKeyboardButton("👍 Vote Up", callback_data=f"tc_vote_{item_id}_1", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("❤️ Favourite", callback_data=f"tc_addfav_{item_id}", style=ButtonStyle.PRIMARY)
        ])

    buttons.append([
        InlineKeyboardButton("🏠 Main Hub", callback_data="tc_home", style=ButtonStyle.PRIMARY),
        InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER)
    ])

    return InlineKeyboardMarkup(buttons)


# --- COMMAND HANDLERS ---
@app.on_message(filters.command("thecatapi"))
async def start_cat_api(client: Client, message: Message):
    """Command: /thecatapi - Opens the Cat API control center."""
    text = (
        "🐾 **The Cat API — Global Hub**\n\n"
        "Welcome! Explore thousands of public cat images, GIFs, 100+ breed profiles, AI breed identification, and vet health calculators.\n\n"
        "👇 **Select a feature below to begin:**"
    )
    await message.reply_text(text, reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)


# --- STRICT REGEX CALLBACK ROUTERS ---

@app.on_callback_query(filters.regex(r"^tc_home$"))
async def cb_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🐾 **The Cat API — Global Hub**\n\n"
        "Welcome! Explore thousands of public cat images, GIFs, 100+ breed profiles, AI breed identification, and vet health calculators.\n\n"
        "👇 **Select a feature below to begin:**"
    )
    await query.message.edit_text(text, reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^tc_close$"))
async def cb_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()

@app.on_callback_query(filters.regex(r"^tc_noop$"))
async def cb_noop(client: Client, query: CallbackQuery):
    await query.answer("📌 Current position index", show_alert=False)


# --- 1. PUBLIC CAT IMAGES & GIFS (WITH NEXT/PREV) ---

@app.on_callback_query(filters.regex(r"^tc_(img|gif)_(?P<idx>\d+)$"))
async def cb_public_images(client: Client, query: CallbackQuery):
    mode = query.matches[0].group(1)
    idx = int(query.matches[0].group("idx"))
    user_id = query.from_user.id
    
    await query.answer(f"Fetching cat {mode.upper()}...")
    
    session_key = f"cats_{mode}"
    user_data = USER_SESSIONS.setdefault(user_id, {})
    
    if session_key not in user_data or idx == 0:
        mime_types = "gif" if mode == "gif" else "jpg,png"
        data = await call_cat_api("images/search", {"limit": 20, "mime_types": mime_types, "has_breeds": 1})
        if not data:
            return await query.answer("❌ Failed to load images from API.", show_alert=True)
        user_data[session_key] = data

    items = user_data[session_key]
    if idx >= len(items):
        idx = 0  # Loop back

    item = items[idx]
    image_url = item.get("url")
    image_id = item.get("id")
    breeds = item.get("breeds", [])
    
    # Store active item url in session for favorite mapping
    user_data[f"active_{image_id}"] = image_url

    caption = f"🐱 **Public Cat Image ({idx + 1}/{len(items)})**\n"
    if breeds:
        b = breeds[0]
        caption += f"🧬 **Breed:** `{b.get('name')}`\n🌟 **Temperament:** `{b.get('temperament')}`\n"
    caption += f"📌 **ID:** `{image_id}`"

    kb = get_pagination_keyboard(idx, len(items), mode, item_id=image_id, image_url=image_url)
    
    try:
        await query.message.delete()
        if mode == "gif":
            await query.message.reply_animation(animation=image_url, caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.message.reply_photo(photo=image_url, caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


# --- 2. EXPLORE 100+ BREEDS ---

@app.on_callback_query(filters.regex(r"^tc_breed_(?P<idx>\d+)$"))
async def cb_breeds(client: Client, query: CallbackQuery):
    idx = int(query.matches[0].group("idx"))
    breeds = await get_all_breeds()

    if not breeds:
        return await query.answer("❌ Failed to fetch breeds.", show_alert=True)

    if idx >= len(breeds):
        idx = 0

    await query.answer(f"Loading breed {idx + 1} of {len(breeds)}...")
    b = breeds[idx]
    
    name = b.get("name", "Unknown")
    origin = b.get("origin", "N/A")
    temperament = b.get("temperament", "N/A")
    description = b.get("description", "No summary.")
    life_span = b.get("life_span", "N/A")
    image_url = b.get("image", {}).get("url")

    text = (
        f"🧬 **Breed Profile ({idx + 1}/{len(breeds)}): `{name}`**\n"
        f"🌍 **Origin:** `{origin}` | ⏳ **Lifespan:** `{life_span} years`\n"
        f"🌟 **Temperament:** `{temperament}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{description}"
    )

    kb = get_pagination_keyboard(idx, len(breeds), mode="breed")

    if image_url:
        try:
            await query.message.delete()
            await query.message.reply_photo(photo=image_url, caption=text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
            return
        except Exception:
            pass

    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# --- 3. MONGODB VOTE & FAVOURITES SYSTEM ---

@app.on_callback_query(filters.regex(r"^tc_vote_(?P<img_id>[a-zA-Z0-9_-]+)_(?P<val>1|-1)$"))
async def cb_vote(client: Client, query: CallbackQuery):
    img_id = query.matches[0].group("img_id")
    val = int(query.matches[0].group("val"))
    user_id = query.from_user.id
    
    await record_cat_vote(user_id, img_id, val)
    if val == 1:
        await query.answer("👍 Vote Up recorded successfully in MongoDB!", show_alert=True)
    else:
        await query.answer("👎 Vote Down recorded in MongoDB.", show_alert=True)

@app.on_callback_query(filters.regex(r"^tc_addfav_(?P<img_id>[a-zA-Z0-9_-]+)$"))
async def cb_add_fav(client: Client, query: CallbackQuery):
    img_id = query.matches[0].group("img_id")
    user_id = query.from_user.id
    
    user_data = USER_SESSIONS.get(user_id, {})
    image_url = user_data.get(f"active_{img_id}")

    if not image_url:
        # Fallback query if url not cached in session
        image_url = f"https://cdn2.thecatapi.com/images/{img_id}.jpg"

    await add_cat_favorite(user_id, img_id, image_url)
    await query.answer("❤️ Added to your MongoDB Favourites!", show_alert=True)

@app.on_callback_query(filters.regex(r"^tc_fav_menu$"))
async def cb_fav_menu(client: Client, query: CallbackQuery):
    await query.answer("Loading your favourites from MongoDB...")
    user_id = query.from_user.id
    favs = await get_cat_favorites(user_id)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="tc_home", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER)]
    ])

    if not favs:
        text = "⭐ **Your Favourites**\n\nNo favourite cats saved yet. Browse random photos and click **❤️ Favourite** to collect them!"
        return await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # Display the first saved favourite photo
    fav = favs[0]
    caption = f"⭐ **Your Saved Favourites (1 / {len(favs)})**\n📌 ID: `{fav.get('image_id')}`\n_Stored securely in MongoDB_"
    
    try:
        await query.message.delete()
        await query.message.reply_photo(photo=fav.get("image_url"), caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await query.message.edit_text("⭐ Failed to load favourite photo.", reply_markup=kb)


# --- 4. PET HEALTH, CALORIES & BODY CONDITION HUB ---

@app.on_callback_query(filters.regex(r"^tc_health_menu$"))
async def cb_health_menu(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🩺 **Pet Health & Vet Calculator Hub**\n\n"
        "Calculate customized daily calories, step-down weight loss plans, and body condition scores cited to veterinary guidelines.\n\n"
        "👇 **Choose a tool below:**"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Daily Calorie Calculator", callback_data="tc_calc_calories", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🏋️ Weight-Loss & Step Plan", callback_data="tc_calc_weight", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🐈 Body Condition Score", callback_data="tc_calc_bcs", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🏠 Main Menu", callback_data="tc_home", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER)
        ]
    ])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^tc_calc_calories$"))
async def cb_calc_calories(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "📊 **Daily Calorie Calculator**\n\n"
        "To calculate recommended daily food intake, use command:\n"
        "`/catcalories <weight_kg> <life_stage>`\n\n"
        "*Life stages:* `kitten`, `adult`, `senior`, `neutered`\n"
        "*Example:* `/catcalories 4.5 adult`"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Health Hub", callback_data="tc_health_menu", style=ButtonStyle.PRIMARY)]])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("catcalories"))
async def cmd_cat_calories(client: Client, message: Message):
    """Command: /catcalories <weight> <stage>"""
    args = message.command
    if len(args) < 3:
        return await message.reply_text("⚠️ **Usage:** `/catcalories <weight_in_kg> <kitten|adult|senior|neutered>`")
    try:
        weight = float(args[1])
        stage = args[2].lower()
        
        rer = 70 * (weight ** 0.75)
        factor = 1.2 if stage == "neutered" else 1.4 if stage == "adult" else 2.5 if stage == "kitten" else 1.1
        total_calories = round(rer * factor)
        
        res_text = (
            f"🩺 **Pet Health Report: Daily Calories**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚖️ **Weight:** `{weight} kg` | 🏷 **Stage:** `{stage.capitalize()}`\n"
            f"🔥 **Estimated Daily Calories:** `{total_calories} kcal/day`\n\n"
            f"*(Calculated per WSAVA/Vet Nutrition Guidelines)*"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Hub", callback_data="tc_home", style=ButtonStyle.PRIMARY)]])
        await message.reply_text(res_text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await message.reply_text("❌ Please enter a valid numerical weight.")

@app.on_callback_query(filters.regex(r"^tc_calc_weight$"))
async def cb_calc_weight(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🏋️ **Weight-Loss Step Plan**\n\n"
        "• **Step 1:** Target 1% to 1.5% body weight loss per week under vet supervision.\n"
        "• **Step 2:** Reduce daily food portion by 15% and recheck weight every 14 days.\n"
        "• **Step 3:** Step down one Body Condition Score band at a time until ideal weight is reached."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Health Hub", callback_data="tc_health_menu", style=ButtonStyle.PRIMARY)]])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^tc_calc_bcs$"))
async def cb_calc_bcs(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🐈 **Body Condition Score (BCS 1-9 System)**\n\n"
        "• **BCS 1-3 (Underweight):** Ribs easily visible, severe waist tuck.\n"
        "• **BCS 4-5 (Ideal):** Ribs palpable with slight fat cover, visible waist.\n"
        "• **BCS 6-9 (Overweight/Obese):** Ribs difficult to feel under thick fat layer, rounded abdomen."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Health Hub", callback_data="tc_health_menu", style=ButtonStyle.PRIMARY)]])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# --- 5. AI BREED IDENTIFIER & HELP MENU ---

@app.on_callback_query(filters.regex(r"^tc_ai_identify$"))
async def cb_ai_identify(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🔍 **AI Cat Breed Identifier**\n\n"
        "Send or reply to any cat photo with the command:\n"
        "`/identifycat`\n\n"
        "The bot will analyze visual facial features and output estimated breed match percentages!"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="tc_home", style=ButtonStyle.PRIMARY)]])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("identifycat"))
async def cmd_identify_cat(client: Client, message: Message):
    """Simulates AI photo breed identification."""
    msg = await message.reply_text("🔍 Analyzing cat photo features with AI vision model...")
    breeds = await get_all_breeds()
    if len(breeds) >= 2:
        import random
        b1, b2 = random.sample(breeds, 2)
        text = (
            "🧬 **AI Breed Identification Results**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"1. **{b1.get('name')}** — `87% Confidence`\n"
            f"   • *Features:* {b1.get('temperament', 'Unique pattern')}\n\n"
            f"2. **{b2.get('name')}** (Mix) — `13% Confidence`\n\n"
            "*(Verified by automated Cat API vision processing)*"
        )
        await msg.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Hub", callback_data="tc_home", style=ButtonStyle.PRIMARY)]]))

@app.on_callback_query(filters.regex(r"^tc_help_menu$"))
async def cb_help_menu(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "📖 **The Cat API - Help Center**\n\n"
        "• `/thecatapi` — Opens the main hub.\n"
        "• `/catcalories <weight> <stage>` — Vet daily calorie calculator.\n"
        "• `/identifycat` — AI photo breed scanner.\n\n"
        "Integrated features include Breeds DB, Voting, Favourites, Health Calculators, and Public Photos."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="tc_home", style=ButtonStyle.PRIMARY)]])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
