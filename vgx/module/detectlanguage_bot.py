import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain DETECT_LANGUAGE_API_KEY

# --- CONFIGURATION & ENDPOINTS ---
DL_BASE = "https://ws.detectlanguage.com/v2"
LANG_CACHE = []  # Caches the 216 languages to keep inline pagination instant


def get_dl_token() -> str:
    """Retrieves the Detect Language API key from config safely."""
    return getattr(Config, "DETECT_LANGUAGE_API_KEY", None)


async def dl_request(method: str, endpoint: str, **kwargs) -> httpx.Response:
    """Centralized async HTTP request helper for Detect Language v2 API."""
    token = get_dl_token()
    url = f"{DL_BASE}/{endpoint.lstrip('/')}"
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers["Accept"] = "application/json"

    async with httpx.AsyncClient() as client:
        try:
            if method.upper() == "POST":
                return await client.post(url, headers=headers, **kwargs)
            elif method.upper() == "GET":
                return await client.get(url, headers=headers, **kwargs)
        except Exception as e:
            print(f"DetectLanguage API Exception [{endpoint}]: {e}")
        return None


# ==========================================
# --- MAIN DASHBOARD MENU BUILDER ---
# ==========================================

def get_dl_main_menu() -> InlineKeyboardMarkup:
    """Interactive dashboard built entirely with Inline Keyboards."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Single Detection", callback_data="dl_help_single"),
            InlineKeyboardButton("📦 Batch Processing", callback_data="dl_help_batch")
        ],
        [
            InlineKeyboardButton("⚡ Clean Code Mode", callback_data="dl_help_code"),
            InlineKeyboardButton("🌐 216 Languages", callback_data="dl_langs_0")
        ],
        [
            InlineKeyboardButton("📊 Account & Usage Quota", callback_data="dl_status"),
            InlineKeyboardButton("❌ Close", callback_data="dl_close")
        ]
    ])


@app.on_message(filters.command(["dl", "detectlanguage", "langhub"]))
async def cmd_dl_dashboard(client: Client, message: Message):
    """Command: /dl - Opens the Detect Language interactive dashboard."""
    text = (
        "🌐 **Detect Language Intelligence Suite**\n\n"
        "Identify languages across single phrases or bulk datasets, browse all **216 supported languages**, "
        "and monitor your real-time API usage quota using the controls below:"
    )
    await message.reply_text(text, reply_markup=get_dl_main_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- 1. SINGLE TEXT ANALYSIS ---
# ==========================================

@app.on_message(filters.command(["detect", "langdetect"]))
async def cmd_dl_single(client: Client, message: Message):
    """Command: /detect <text> - Full language analysis with confidence & reliability."""
    text_input = message.text.partition(" ")[2].strip()
    if not text_input and message.reply_to_message:
        text_input = (message.reply_to_message.text or message.reply_to_message.caption or "").strip()

    if not text_input:
        return await message.reply_text(
            "⚠️ **Usage:** `/detect <text>` (or reply to any message)\n\n"
            "_Example:_ `/detect Bonjour tout le monde`",
            parse_mode=ParseMode.MARKDOWN
        )

    msg = await message.reply_text("🔍 Analyzing text language...")
    resp = await dl_request("POST", "detect", json={"q": text_input}, timeout=15.0)

    if not resp or resp.status_code != 200:
        return await msg.edit_text("❌ Detection failed. Verify `DETECT_LANGUAGE_API_KEY` in `config.py`.")

    detections = resp.json().get("data", {}).get("detections", [])
    if not detections:
        return await msg.edit_text("🤷 Could not identify a language for the provided text.")

    lines = ["🔍 **Language Detection Analysis**\n"]
    for idx, item in enumerate(detections[:3], start=1):
        lang = item.get("language", "unknown").upper()
        confidence = item.get("confidence", 0)
        reliable = "✅ Reliable" if item.get("isReliable") else "⚠️ Low Reliability"
        lines.append(f"**{idx}. `{lang}`** — Confidence: `{confidence}` ({reliable})")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Extract Clean Code", callback_data="dl_help_code"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="dl_home")
        ]
    ])
    await msg.edit_text("\n".join(lines), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- 2. CLEAN CODE EXTRACTION ---
# ==========================================

@app.on_message(filters.command(["detectcode", "langcode"]))
async def cmd_dl_clean_code(client: Client, message: Message):
    """Command: /detectcode <text> - Lightweight extraction returning only the ISO language code."""
    text_input = message.text.partition(" ")[2].strip()
    if not text_input and message.reply_to_message:
        text_input = (message.reply_to_message.text or message.reply_to_message.caption or "").strip()

    if not text_input:
        return await message.reply_text(
            "⚠️ **Usage:** `/detectcode <text>`\n\n"
            "_Example:_ `/detectcode こんにちは世界`",
            parse_mode=ParseMode.MARKDOWN
        )

    msg = await message.reply_text("⚡ Extracting ISO code...")
    resp = await dl_request("POST", "detect", json={"q": text_input}, timeout=15.0)

    if not resp or resp.status_code != 200:
        return await msg.edit_text("❌ Failed to extract language code.")

    detections = resp.json().get("data", {}).get("detections", [])
    code = detections[0].get("language", "unknown") if detections else "unknown"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="dl_home")]])
    await msg.edit_text(
        f"⚡ **ISO Language Code:** `{code}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# ==========================================
# --- 3. BATCH PROCESSING ---
# ==========================================

@app.on_message(filters.command(["batchdetect", "dlbatch"]))
async def cmd_dl_batch(client: Client, message: Message):
    """Command: /batchdetect <line1> \\n <line2> - Bulk multi-lingual detection in one request."""
    raw_block = message.text.partition(" ")[2].strip()
    if not raw_block and message.reply_to_message:
        raw_block = (message.reply_to_message.text or "").strip()

    items = [line.strip() for line in raw_block.splitlines() if line.strip()]
    if len(items) < 2:
        return await message.reply_text(
            "⚠️ **Batch Usage:** Send at least 2 lines of text:\n\n"
            "```\n/batchdetect\nHello world\nHola mundo\nBonjour le monde\n```",
            parse_mode=ParseMode.MARKDOWN
        )

    msg = await message.reply_text(f"📦 Processing batch of **{len(items)}** items...")
    resp = await dl_request("POST", "detect", json={"q": items}, timeout=20.0)

    if not resp or resp.status_code != 200:
        return await msg.edit_text("❌ Batch detection failed.")

    batch_results = resp.json().get("data", {}).get("detections", [])
    output_lines = [f"📦 **Batch Detection Results ({len(items)} items)**\n"]

    for idx, (snippet, det_list) in enumerate(zip(items, batch_results), start=1):
        if det_list:
            top = det_list[0]
            lang = top.get("language", "??").upper()
            conf = top.get("confidence", 0)
            rel = "✅" if top.get("isReliable") else "⚠️"
            preview = snippet[:32] + ("..." if len(snippet) > 32 else "")
            output_lines.append(f"**{idx}.** `{preview}`\n   ↳ **{lang}** | Conf: `{conf}` {rel}")
        else:
            output_lines.append(f"**{idx}.** `{snippet[:32]}` ↳ `Unknown`")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="dl_home")]])
    await msg.edit_text("\n".join(output_lines[:25]), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- 4. GLOBAL LANGUAGE DIRECTORY (216) ---
# ==========================================

async def fetch_supported_languages() -> list:
    """Fetches and caches the 216 supported languages from Detect Language API."""
    global LANG_CACHE
    if LANG_CACHE:
        return LANG_CACHE

    resp = await dl_request("GET", "languages", timeout=15.0)
    if resp and resp.status_code == 200:
        LANG_CACHE = resp.json()
    return LANG_CACHE


def build_languages_page(page: int = 0, per_page: int = 24) -> tuple:
    """Builds a paginated inline directory of supported languages."""
    total = len(LANG_CACHE)
    start = page * per_page
    end = start + per_page
    slice_items = LANG_CACHE[start:end]

    text = f"🌐 **Supported Languages Directory ({total} Total)**\n_Page {page + 1} of {(total - 1) // per_page + 1}_\n\n"
    for item in slice_items:
        code = item.get("code", "")
        name = item.get("name", "")
        text += f"• `{code}` — {name}\n"

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"dl_langs_{page - 1}"))
    if end < total:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"dl_langs_{page + 1}"))

    buttons = []
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="dl_home")])

    return text, InlineKeyboardMarkup(buttons)


@app.on_message(filters.command(["languages", "dllangs"]))
async def cmd_dl_languages(client: Client, message: Message):
    """Command: /languages - Lists all 216 supported languages."""
    msg = await message.reply_text("🌐 Fetching 216 supported languages...")
    langs = await fetch_supported_languages()
    if not langs:
        return await msg.edit_text("❌ Unable to load the supported languages directory.")

    text, keyboard = build_languages_page(page=0)
    await msg.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- 5. ACCOUNT & USAGE ANALYTICS ---
# ==========================================

async def fetch_account_status_text() -> str:
    """Queries /v2/user/status and formats plan, quota, and health analytics."""
    resp = await dl_request("GET", "user/status", timeout=15.0)
    if not resp or resp.status_code != 200:
        return "❌ Failed to retrieve account quota. Verify `DETECT_LANGUAGE_API_KEY`."

    data = resp.json()
    status = data.get("status", "UNKNOWN")
    status_badge = "🟢 ACTIVE" if status == "ACTIVE" else f"🔴 {status}"

    requests_used = data.get("requests", 0)
    daily_req_limit = data.get("daily_requests_limit", "Unlimited")
    bytes_used = data.get("bytes", 0)
    daily_bytes_limit = data.get("daily_bytes_limit", "Unlimited")
    plan = data.get("plan", "Free")
    plan_expires = data.get("plan_expires") or "Never / N/A"
    date_str = data.get("date", "Today")

    return (
        f"📊 **Detect Language Account & Usage Analytics**\n\n"
        f"• **Account Health:** {status_badge}\n"
        f"• **Active Plan:** `{plan}`\n"
        f"• **Plan Expiration:** `{plan_expires}`\n"
        f"• **Billing Date:** `{date_str}`\n\n"
        f"**Daily Quota Usage:**\n"
        f"• **Requests:** `{requests_used}` / `{daily_req_limit}`\n"
        f"• **Text Bytes:** `{bytes_used:,}` / `{daily_bytes_limit:,}` bytes"
    )


@app.on_message(filters.command(["dlstatus", "dlquota"]))
async def cmd_dl_status(client: Client, message: Message):
    """Command: /dlstatus - Shows account health, plan details, and daily quota usage."""
    msg = await message.reply_text("📊 Fetching account usage metrics...")
    text = await fetch_account_status_text()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh Quota", callback_data="dl_status")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="dl_home")]
    ])
    await msg.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE INLINE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^dl_home$"))
async def cb_dl_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🌐 **Detect Language Intelligence Suite**\n\n"
        "Select a tool or view your live API quota below:"
    )
    await query.message.edit_text(text, reply_markup=get_dl_main_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^dl_help_single$"))
async def cb_dl_help_single(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="dl_home")]])
    await query.message.edit_text(
        "🔍 **Single Text Analysis**\n\n"
        "Analyze any phrase or reply to any message to get its ISO code, confidence score, and reliability:\n\n"
        "`/detect Das ist ein wunderbarer Tag`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^dl_help_batch$"))
async def cb_dl_help_batch(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="dl_home")]])
    await query.message.edit_text(
        "📦 **Batch Multi-Lingual Processing**\n\n"
        "Send multiple lines in one command to analyze them in a single bulk API call:\n\n"
        "```\n/batchdetect\nGood morning\nBuenos días\nおはようございます\n```",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^dl_help_code$"))
async def cb_dl_help_code(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="dl_home")]])
    await query.message.edit_text(
        "⚡ **Clean Code Extraction**\n\n"
        "Returns only the lightweight ISO 639 language code without extra metadata:\n\n"
        "`/detectcode Привет, как дела?`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^dl_langs_(?P<page>\d+)$"))
async def cb_dl_langs_page(client: Client, query: CallbackQuery):
    page = int(query.matches[0].group("page"))
    await query.answer("Loading languages...")
    langs = await fetch_supported_languages()
    if not langs:
        return await query.answer("Failed to load languages.", show_alert=True)

    text, keyboard = build_languages_page(page=page)
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^dl_status$"))
async def cb_dl_status(client: Client, query: CallbackQuery):
    await query.answer("Refreshing quota...")
    text = await fetch_account_status_text()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh Quota", callback_data="dl_status")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="dl_home")]
    ])
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^dl_close$"))
async def cb_dl_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
