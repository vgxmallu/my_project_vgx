import io
import time
import os
import httpx
import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# In-memory caches for session pagination and filter state
CAT_CACHE = []
USER_STATE = {}  # Stores user customization settings (filter, size, type, etc.)

BASE_CATAAS = "https://cataas.com/cat"



# --- SAFE API FETCH WITH FALLBACK ---
async def fetch_cat_records():
    global CAT_CACHE
    if CAT_CACHE:
        return CAT_CACHE
    url = "https://cataas.com/api/cats?limit=50"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 200:
                CAT_CACHE = resp.json()
                return CAT_CACHE
        except Exception:
            pass
        return []

async def fetch_available_tags():
    """Fetches popular cat tags from Cataas."""
    url = "https://cataas.com/api/tags"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            return response.json()[:12] # Top 12 tags for clean UI
        except Exception:
            return ["cute", "sleepy", "fluffy", "kitten", "White", "orange"]


# --- HELPER TO BUILD URL WITH CACHE-BUSTING ---
def build_cat_url(cat_id: str = None, tag: str = None, says: str = None, user_settings: dict = None, is_gif: bool = False) -> str:
    url = "https://cataas.com/cat"
    
    if is_gif:
        url += "/gif"
    elif tag:
        url += f"/{tag}"
    if says:
        formatted_text = says.replace(" ", "%20")
        url += f"/says/{formatted_text}"
    elif cat_id and not tag and not is_gif:
        url += f"/{cat_id}"

    params = []
    if user_settings:
        if user_settings.get("width"):
            params.append(f"width={user_settings['width']}")
        if user_settings.get("height"):
            params.append(f"height={user_settings['height']}")
        if user_settings.get("type"):
            params.append(f"type={user_settings['type']}")
        if user_settings.get("filter"):
            f_val = user_settings['filter']
            if f_val == "custom":
                params.append("filter=custom&r=255&g=100&b=50")
            else:
                params.append(f"filter={f_val}")

    # Unique timestamp cache-buster
    params.append(f"t={int(time.time() * 1000)}")

    if params:
        url += "?" + "&".join(params)

    return url


# --- SAFE RANDOM CAT HANDLER WITH 502 ERROR FALLBACK ---
@app.on_callback_query(filters.regex(r"^cat_random$"))
async def cb_cat_random(client: Client, query: CallbackQuery):
    await query.answer("Fetching a fresh random cat...")
    user_id = query.from_user.id
    settings = USER_STATE.get(user_id, {})
    
    # Try direct endpoint first with cache buster
    url = f"https://cataas.com/cat?t={int(time.time() * 1000)}"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Another Random", callback_data="cat_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="cat_home"), InlineKeyboardButton("❌ Close", callback_data="cat_close")]
    ])
    
    async with httpx.AsyncClient() as client_http:
        try:
            resp = await client_http.get(url, timeout=15.0)
            if resp.status_code == 200:
                photo_bytes = io.BytesIO(resp.content)
                photo_bytes.name = "cat.jpg"
                
                await query.message.delete()
                await query.message.reply_photo(
                    photo=photo_bytes,
                    caption="🐱 **Random Cat Image**\n_One link, one cat. That's it._",
                    reply_markup=kb,
                    parse_mode=ParseMode.MARKDOWN
                )
                return
        except Exception:
            pass
            
    # Fallback: If Cataas server returns 502, pull from cached gallery records instead!
    cats = await fetch_cat_records()
    if cats:
        import random
        cat = random.choice(cats)
        fallback_url = f"https://cataas.com/cat/{cat.get('_id')}?t={int(time.time() * 1000)}"
        try:
            async with httpx.AsyncClient() as client_http:
                resp = await client_http.get(fallback_url, timeout=15.0)
                if resp.status_code == 200:
                    photo_bytes = io.BytesIO(resp.content)
                    photo_bytes.name = "cat.jpg"
                    await query.message.delete()
                    await query.message.reply_photo(
                        photo=photo_bytes,
                        caption="🐱 **Random Cat Image (From Cache)**\n_Cataas server was busy, loaded from backup!_",
                        reply_markup=kb,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
        except Exception:
            pass

    await query.answer("⚠️ Cataas servers are currently experiencing heavy traffic (502 Gateway). Please try again in a moment!", show_alert=True)


# --- SAFE ANIMATED GIF HANDLER WITH FALLBACK ---
@app.on_callback_query(filters.regex(r"^cat_gif$"))
async def cb_cat_gif(client: Client, query: CallbackQuery):
    await query.answer("Fetching an animated cat GIF...")
    url = f"https://cataas.com/cat/gif?t={int(time.time() * 1000)}"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Another GIF", callback_data="cat_gif")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="cat_home"), InlineKeyboardButton("❌ Close", callback_data="cat_close")]
    ])
    
    async with httpx.AsyncClient() as client_http:
        try:
            resp = await client_http.get(url, timeout=20.0)
            if resp.status_code == 200:
                gif_bytes = io.BytesIO(resp.content)
                gif_bytes.name = "cat.gif"
                
                await query.message.delete()
                await query.message.reply_animation(
                    animation=gif_bytes,
                    caption="🎬 **Animated Cat GIF**\n_One link, one cat. That's it._",
                    reply_markup=kb,
                    parse_mode=ParseMode.MARKDOWN
                )
                return
        except Exception:
            pass

    await query.answer("⚠️ Cataas GIF server is temporarily busy (502 Gateway). Please try again shortly!", show_alert=True)


# --- UI KEYBOARD BUILDERS ---
def get_main_menu():
    """Main interactive hub for Cataas module."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🐱 Random Cat", callback_data="cat_random"),
            InlineKeyboardButton("🎬 Cat GIF", callback_data="cat_gif")
        ],
        [
            InlineKeyboardButton("📂 Browse Gallery (Next/Prev)", callback_data="cat_gallery_0"),
            InlineKeyboardButton("🏷️ Filter by Tag", callback_data="cat_tags_menu")
        ],
        [
            InlineKeyboardButton("💬 Create Text Meme", callback_data="cat_meme_prompt"),
            InlineKeyboardButton("⚙️ Custom Filters & Layout", callback_data="cat_settings_menu")
        ],
        [
            InlineKeyboardButton("📖 Help & Info", callback_data="cat_help_menu"),
            InlineKeyboardButton("❌", callback_data="close")
        ]
    ])

def get_pagination_keyboard(index: int, total: int, mode: str = "gallery", target: str = ""):
    """Next and Prev navigation keyboard exclusively using callback_data."""
    prev_idx = max(0, index - 1)
    next_idx = min(total - 1, index + 1)

    prefix = f"cat_{mode}_{target}" if target else f"cat_{mode}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}_{prev_idx}"),
            InlineKeyboardButton(f"🖼️ {index + 1} / {total}", callback_data="cat_noop"),
            InlineKeyboardButton("Next ➡️", callback_data=f"{prefix}_{next_idx}")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="cat_settings_menu"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="cat_home")
        ],
        [
            InlineKeyboardButton("❌", callback_data="close")
        ]
    ])

def get_settings_keyboard(settings: dict):
    """Settings menu for resizing, layout types, and visual filters."""
    cur_filter = settings.get("filter", "None")
    cur_type = settings.get("type", "Standard")
    cur_size = settings.get("size", "Default")

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🎨 Filter: {str(cur_filter).capitalize()}", callback_data="cat_set_filter_toggle"),
            InlineKeyboardButton(f"📐 Type: {str(cur_type).capitalize()}", callback_data="cat_set_type_toggle")
        ],
        [
            InlineKeyboardButton(f"📏 Size: {cur_size}", callback_data="cat_set_size_toggle"),
            InlineKeyboardButton("🔄 Reset All", callback_data="cat_set_reset")
        ],
        [
            InlineKeyboardButton("🏠 Back to Main Menu", callback_data="cat_home")
        ]
    ])


# --- COMMAND HANDLERS ---
@app.on_message(filters.command("cats"))
async def cats_command(client: Client, message: Message):
    """Command: /cats - Opens the Cataas Control Center."""
    user_id = message.from_user.id
    USER_STATE[user_id] = {"filter": None, "type": None, "size": "Default", "width": None, "height": None}

    welcome_text = (
        "🐱 **CATAAS — Cat as a Service**\n"
        "_Serves random cat images and GIFs, with text, filters and tags. One link, one cat. That's it._ 🐾\n\n"
        "Welcome! Explore endless cat photos, GIFs, tag filters, custom text memes, and visual effects.\n\n"
        "👇 **Select an option below to begin:**"
    )
    await message.reply_text(welcome_text, reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("catshelp"))
async def cats_help_command(client: Client, message: Message):
    """Command: /catshelp - Displays official Cataas information."""
    help_text = (
        "📖 **CATAAS — Help & Documentation**\n\n"
        "_“CATAAS — Cat as a Service — serves random cat images and GIFs, with text, filters and tags. One link, one cat. That's it.”_\n\n"
        "**Features Included:**\n"
        "• **Random Cat / GIF:** Instant streaming via direct service endpoints.\n"
        "• **Gallery Navigation:** Use `Next` and `Prev` buttons to browse cat records seamlessly.\n"
        "• **Tag Filters:** Filter cats by keywords (`cute`, `sleepy`, `fluffy`, etc.).\n"
        "• **Text Memes (`/catsays`):** Overlay custom messages directly onto cat photos.\n"
        "• **Customization & Filters:** Apply blur, mono, negate, custom RGB, or adjust layout dimensions (`square`, `400x300`, etc.)."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="cat_home")]])
    await message.reply_text(help_text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# --- STRICT REGEX CALLBACK ROUTERS ---

@app.on_callback_query(filters.regex(r"^cat_home$"))
async def cb_cat_home(client: Client, query: CallbackQuery):
    await query.answer()
    welcome_text = (
        "🐱 **CATAAS — Cat as a Service**\n"
        "_Serves random cat images and GIFs, with text, filters and tags. One link, one cat. That's it._ 🐾\n\n"
        "Welcome! Explore endless cat photos, GIFs, tag filters, custom text memes, and visual effects.\n\n"
        "👇 **Select an option below to begin:**"
    )
    await query.message.edit_text(welcome_text, reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^cat_help_menu$"))
async def cb_cat_help(client: Client, query: CallbackQuery):
    await query.answer()
    help_text = (
        "📖 **CATAAS — Help & Documentation**\n\n"
        "_“CATAAS — Cat as a Service — serves random cat images and GIFs, with text, filters and tags. One link, one cat. That's it.”_\n\n"
        "**Features Included:**\n"
        "• **Random Cat / GIF:** Instant streaming via direct service endpoints.\n"
        "• **Gallery Navigation:** Use `Next` and `Prev` buttons to browse cat records seamlessly.\n"
        "• **Tag Filters:** Filter cats by keywords (`cute`, `sleepy`, `fluffy`, etc.).\n"
        "• **Text Memes (`/catsays`):** Overlay custom messages directly onto cat photos.\n"
        "• **Customization & Filters:** Apply blur, mono, negate, custom RGB, or adjust layout dimensions."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="cat_home")]])
    await query.message.edit_text(help_text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^cat_noop$"))
async def cb_cat_noop(client: Client, query: CallbackQuery):
    await query.answer("📌 Cataas Gallery Index", show_alert=False)

@app.on_callback_query(filters.regex(r"^cat_gallery_(?P<idx>\d+)$"))
async def cb_cat_gallery(client: Client, query: CallbackQuery):
    idx = int(query.matches[0].group("idx"))
    user_id = query.from_user.id
    settings = USER_STATE.get(user_id, {})

    cats = await fetch_cat_records()
    if not cats or idx >= len(cats):
        return await query.answer("⚠️ End of gallery reached.", show_alert=True)

    await query.answer(f"Loading cat {idx + 1} of {len(cats)}...")
    cat = cats[idx]
    cat_id = cat.get("_id")
    url = build_cat_url(cat_id=cat_id, user_settings=settings)

    kb = get_pagination_keyboard(idx, len(cats), mode="gallery")
    
    try:
        await query.message.delete()
        tags_str = ", ".join(cat.get("tags", ["cat"]))
        await query.message.reply_photo(
            photo=url,
            caption=f"🖼️ **Cat Gallery Record**\n🏷️ **Tags:** `{tags_str}`\n_One link, one cat. That's it._",
            reply_markup=kb,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

@app.on_callback_query(filters.regex(r"^cat_tags_menu$"))
async def cb_cat_tags_menu(client: Client, query: CallbackQuery):
    await query.answer("Loading tags...")
    tags = await fetch_available_tags()

    keyboard = []
    row = []
    for tag in tags:
        row.append(InlineKeyboardButton(f"🏷️ {tag.capitalize()}", callback_data=f"cat_tag_{tag}_0"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="cat_home")])

    await query.message.edit_text(
        "🏷️ **Select a Cat Tag Category:**\n_Serves random cat images filtered by tags._",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.regex(r"^cat_tag_(?P<tag>[a-zA-Z]+)_(?P<idx>\d+)$"))
async def cb_cat_tag_pagination(client: Client, query: CallbackQuery):
    tag = query.matches[0].group("tag")
    idx = int(query.matches[0].group("idx"))
    user_id = query.from_user.id
    settings = USER_STATE.get(user_id, {})

    url_api = f"https://cataas.com/api/cats?tags={tag}&limit=30"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url_api)
        cats = resp.json() if resp.status_code == 200 else []

    if not cats or idx >= len(cats):
        return await query.answer(f"⚠️ No more cats found for tag '{tag}'.", show_alert=True)

    await query.answer(f"Loading {tag} cat {idx + 1}...")
    cat = cats[idx]
    cat_id = cat.get("_id")
    url = build_cat_url(cat_id=cat_id, tag=tag, user_settings=settings)

    kb = get_pagination_keyboard(idx, len(cats), mode="tag", target=tag)
    
    try:
        await query.message.delete()
        await query.message.reply_photo(
            photo=url,
            caption=f"🏷️ **Tag Category:** `{tag.capitalize()}`\n🖼️ Record `{idx + 1}/{len(cats)}`",
            reply_markup=kb,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

@app.on_callback_query(filters.regex(r"^cat_meme_prompt$"))
async def cb_cat_meme_prompt(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        "💬 **Create Custom Text Overlay Meme**\n\n"
        "To generate a cat image with custom text overlaid, use the command:\n"
        "`/catsays <your message>`\n\n"
        "*Example:* `/catsays Hello World` or `/catsays Boss Mode`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="cat_home")]]),
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.command("catsays"))
async def catsays_command(client: Client, message: Message):
    """Command: /catsays <text> - Generates a cat meme with custom text overlay."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/catsays <your text>`\nExample: `/catsays Hello Telegram`")

    text_msg = " ".join(args[1:])
    user_id = message.from_user.id
    settings = USER_STATE.get(user_id, {})

    url = build_cat_url(says=text_msg, user_settings=settings)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="cat_home"), InlineKeyboardButton("❌ Close", callback_data="cat_close")]
    ])

    await message.reply_photo(
        photo=url,
        caption=f"💬 **Cat Meme Overlay:**\n`{text_msg}`\n_One link, one cat. That's it._",
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.regex(r"^cat_settings_menu$"))
async def cb_cat_settings(client: Client, query: CallbackQuery):
    await query.answer()
    user_id = query.from_user.id
    settings = USER_STATE.setdefault(user_id, {"filter": None, "type": None, "size": "Default"})

    await query.message.edit_text(
        "⚙️ **Image Customization & Query Parameters**\n\n"
        "Configure layout sizes, preset types, and visual filters below:",
        reply_markup=get_settings_keyboard(settings)
    )

@app.on_callback_query(filters.regex(r"^cat_set_filter_toggle$"))
async def cb_set_filter(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    settings = USER_STATE.setdefault(user_id, {})
    
    filters_list = [None, "blur", "mono", "negate", "custom"]
    current = settings.get("filter")
    next_idx = (filters_list.index(current) + 1) % len(filters_list) if current in filters_list else 1
    settings["filter"] = filters_list[next_idx]

    await query.answer(f"Filter set to: {str(settings['filter']).capitalize()}")
    await query.message.edit_reply_markup(reply_markup=get_settings_keyboard(settings))

@app.on_callback_query(filters.regex(r"^cat_set_type_toggle$"))
async def cb_set_type(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    settings = USER_STATE.setdefault(user_id, {})
    
    types_list = [None, "square", "small", "xsmall"]
    current = settings.get("type")
    next_idx = (types_list.index(current) + 1) % len(types_list) if current in types_list else 1
    settings["type"] = types_list[next_idx]

    await query.answer(f"Layout type set to: {str(settings['type']).capitalize()}")
    await query.message.edit_reply_markup(reply_markup=get_settings_keyboard(settings))

@app.on_callback_query(filters.regex(r"^cat_set_size_toggle$"))
async def cb_set_size(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    settings = USER_STATE.setdefault(user_id, {})
    
    if settings.get("width") == 400:
        settings["width"] = 600
        settings["height"] = 400
        settings["size"] = "600x400"
    elif settings.get("width") == 600:
        settings["width"] = None
        settings["height"] = None
        settings["size"] = "Default"
    else:
        settings["width"] = 400
        settings["height"] = 300
        settings["size"] = "400x300"

    await query.answer(f"Dimensions set to: {settings['size']}")
    await query.message.edit_reply_markup(reply_markup=get_settings_keyboard(settings))

@app.on_callback_query(filters.regex(r"^cat_set_reset$"))
async def cb_set_reset(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    USER_STATE[user_id] = {"filter": None, "type": None, "size": "Default", "width": None, "height": None}
    
    await query.answer("🔄 Settings reset to default!", show_alert=True)
    await query.message.edit_reply_markup(reply_markup=get_settings_keyboard(USER_STATE[user_id]))
