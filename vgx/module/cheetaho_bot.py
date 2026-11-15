import io
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config

# --- CONFIGURATION ---
CHEETAHO_API_URL = "https://api.cheetaho.com/v1/optimize"


def safe_truncate(text: str, max_length: int = 3800) -> str:
    """Safely truncates text to stay well within Telegram's 4000 character limit."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n... _(Output truncated due to length limitations)_"


async def cheetaho_optimize_request(source, is_url: bool = True, options: dict = None) -> dict:
    """Helper utility for asynchronous optimization requests to CheetahO API via URL or File Upload."""
    headers = {
        "Authorization": f"Bearer {getattr(Config, 'CHEETAHO_API_KEY')}",
        "Accept": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        try:
            if is_url:
                headers["Content-Type"] = "application/json"
                payload = {"url": source}
                if options:
                    payload.update(options)
                response = await client.post(CHEETAHO_API_URL, json=payload, headers=headers)
            else:
                # Multipart file upload for local attachments
                files = {"file": ("image.jpg", source, "image/jpeg")}
                response = await client.post(CHEETAHO_API_URL, data=options or {}, files=files, headers=headers)

            if response.status_code in [200, 201]:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "status": response.status_code, "error": safe_truncate(response.text, max_length=1500)}
        except Exception as e:
            return {"success": False, "status": 500, "error": str(e)}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_cheetaho_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for CheetahO Image Optimization controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Lossless Optimize", callback_data="ch_lossless"),
            InlineKeyboardButton("⚡ WebP Compression", callback_data="ch_webp")
        ],
        [
            InlineKeyboardButton("📐 Resize & Quality", callback_data="ch_resize"),
            InlineKeyboardButton("📚 CheetahO Docs", url="https://cheetaho.com/docs")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="ch_close")]
    ])


@app.on_message(filters.command(["cheetaho", "optimize", "compress"]))
async def cmd_cheetaho_dashboard(client: Client, message: Message):
    """Command: /cheetaho - Opens the master interactive CheetahO Image Optimization suite."""
    text = (
        "⚡ **CheetahO Image Intelligence Suite**\n\n"
        "Optimize, compress, resize, and convert JPEG, PNG, or GIF files seamlessly with lossless & lossy algorithms.\n\n"
        "👉 **How to use:** Send any photo/image document with caption `/compress` or pass a live URL using `/opturl <url>`."
    )
    await message.reply_text(safe_truncate(text), reply_markup=get_cheetaho_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND & FILE UPLOAD HANDLERS ---
# ==========================================

@app.on_message(filters.command(["opturl", "cheetahourl"]))
async def cmd_cheetaho_url(client: Client, message: Message):
    """Command: /opturl <image_url> - Optimizes a live image URL via CheetahO API."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/opturl <direct_image_url>`\n\n_Example:_ `/opturl https://example.com/photo.jpg`",
            parse_mode=ParseMode.MARKDOWN
        )

    target_url = message.text.partition(" ")[2].strip()
    msg = await message.reply_text(f"🔄 Processing URL image optimization via CheetahO...")

    res = await cheetaho_optimize_request(target_url, is_url=True, options={"quality": "lossless"})
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ch_home")]])

    if not res["success"]:
        return await msg.edit_text(
            f"❌ **Optimization Failed** (`{res.get('status', 500)}`):\n`{safe_truncate(res['error'])}`\n\n"
            "_Tip: Check your API credentials in `config.py`._",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    data = res["data"]
    response_text = (
        f"✅ **URL OPTIMIZATION COMPLETE**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Original Size:** `{data.get('original_size', 'N/A')}`\n"
        f"• **Optimized Size:** `{data.get('optimized_size', 'N/A')}`\n"
        f"• **Savings:** `{data.get('percent_saved', 'N/A')}%`\n"
        f"• **Download URL:** `{data.get('optimized_url', target_url)}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await msg.edit_text(safe_truncate(response_text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.photo | filters.document)
async def handle_cheetaho_file_upload(client: Client, message: Message):
    """Interceps local photo/document uploads when captioned with /compress or /optimize."""
    caption = message.caption or ""
    if not any(cmd in caption.lower() for cmd in ["/compress", "/optimize", "/cheetaho"]):
        return

    msg = await message.reply_text("⏳ Downloading and compressing local image via CheetahO...")

    try:
        file_obj = message.photo or message.document
        downloaded_file = await client.download_media(file_obj, in_memory=True)
        image_bytes = downloaded_file.getbuffer().tobytes()

        # Send raw bytes via multipart/form-data request
        res = await cheetaho_optimize_request(image_bytes, is_url=False, options={"quality": "lossy"})
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ch_home")]])

        if not res["success"]:
            return await msg.edit_text(
                f"❌ **Local Compression Failed** (`{res.get('status', 500)}`):\n`{safe_truncate(res['error'])}`\n\n"
                "_Tip: Ensure your file is under 4MB and API key is valid._",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )

        data = res["data"]
        response_text = (
            f"✅ **LOCAL COMPRESSION COMPLETE**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• **Original Size:** `{data.get('original_size', 'N/A')}`\n"
            f"• **Optimized Size:** `{data.get('optimized_size', 'N/A')}`\n"
            f"• **Savings:** `{data.get('percent_saved', 'N/A')}%`\n"
            f"• **Optimized File URL:** `{data.get('optimized_url', 'Available in panel')}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

        await msg.edit_text(safe_truncate(response_text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await msg.edit_text(f"❌ Error uploading image file:\n`{safe_truncate(str(e))}`", parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^ch_home$"))
async def cb_ch_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "⚡ **CheetahO Image Intelligence Suite**\n\n"
        "Optimize, compress, resize, and convert JPEG, PNG, or GIF files seamlessly with lossless & lossy algorithms.\n\n"
        "👉 **How to use:** Send any photo/image document with caption `/compress` or pass a live URL using `/opturl <url>`."
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=get_cheetaho_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^ch_lossless$"))
async def cb_ch_lossless(client: Client, query: CallbackQuery):
    await query.answer("Configuring lossless profile...")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Test Sample URL", callback_data="ch_test_sample")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="ch_home")]
    ])
    text = (
        "📉 **Lossless Image Optimization**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Reduces file sizes without losing a single pixel of quality. Ideal for logos and master artwork.\n\n"
        "👉 Run `/opturl <url>` or upload a photo with caption `/compress`."
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^ch_webp$"))
async def cb_ch_webp(client: Client, query: CallbackQuery):
    await query.answer("Configuring WebP container...")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="ch_home")]
    ])
    text = (
        "🌐 **WebP Format Compression**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Converts raster assets into next-gen WebP containers, achieving up to 35% higher compression than standard JPEGs with full alpha transparency."
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^ch_resize$"))
async def cb_ch_resize(client: Client, query: CallbackQuery):
    await query.answer("Loading resize parameters...")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="ch_home")]
    ])
    text = (
        "📐 **Image Resizing & Quality Tuning**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "• **Custom Quality:** Adjustable scale (1-100)\n"
        "• **Dimensions:** Pass strict `width` and `height` constraints dynamically in your API payload parameters."
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^ch_test_sample$"))
async def cb_ch_test_sample(client: Client, query: CallbackQuery):
    await query.answer("Simulating sample optimization...")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ch_home")]])
    text = (
        "📊 **SIMULATED OPTIMIZATION RESULT**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "• **Status:** `HTTP 200 OK`\n"
        "• **Original:** `480 KB`\n"
        "• **Optimized:** `92 KB` _(Saved 81%)_\n"
        "• **Format:** `JPEG Lossless`\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^ch_close$"))
async def cb_ch_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
