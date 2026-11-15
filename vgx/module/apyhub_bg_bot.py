import io
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config

# --- CONFIGURATION ---
APYHUB_API_URL = "https://api.eu.apyhub.com/apyhub/change-image-background/multi-part/download"


def safe_truncate(text: str, max_length: int = 3800) -> str:
    """Safely truncates text to stay well within Telegram's 4000 character limit."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n... _(Output truncated due to length limitations)_"


async def remove_background_request(image_bytes: bytes, filename: str = "image.png") -> dict:
    """Sends multipart file upload request to ApyHub background removal endpoint."""
    headers = {
        "apy-token": Config.APY_HUB_TOKEN,
        "Accept": "application/octet-stream"
    }
    files = {"image": (filename, image_bytes, "image/png")}
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(APYHUB_API_URL, headers=headers, files=files)
            if response.status_code == 200:
                return {"success": True, "content": response.content}
            else:
                return {"success": False, "status": response.status_code, "error": safe_truncate(response.text, max_length=1500)}
        except Exception as e:
            return {"success": False, "status": 500, "error": str(e)}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_apyhub_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for ApyHub Background Removal controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼️ Remove Background Guide", callback_data="apy_guide"),
            InlineKeyboardButton("📚 ApyHub Docs", url="https://apyhub.com/utility/change-image-background")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="apy_close")]
    ])


@app.on_message(filters.command(["removebg", "bgremove", "apyhub"]))
async def cmd_apyhub_dashboard(client: Client, message: Message):
    """Command: /removebg - Opens the interactive ApyHub background removal suite."""
    text = (
        "✂️ **ApyHub Image Background Removal Suite**\n\n"
        "Remove backgrounds from photos instantly at scale using multipart API integration.\n\n"
        "👉 **How to use:** Send any photo or image attachment with caption `/removebg` to process it automatically!"
    )
    await message.reply_text(safe_truncate(text), reply_markup=get_apyhub_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- FILE & PHOTO HANDLER ---
# ==========================================

@app.on_message(filters.photo | filters.document)
async def handle_image_background_removal(client: Client, message: Message):
    """Automatically intercepts photos or image documents when /removebg is present or sent as reply."""
    # Check if command or caption contains trigger
    caption = message.caption or ""
    if not (message.command or "/removebg" in caption or "/bgremove" in caption):
        return

    msg = await message.reply_text("⏳ Downloading and removing background via ApyHub...")

    try:
        # Download photo or document stream into memory byte buffer
        file_obj = message.photo or message.document
        downloaded_file = await client.download_media(file_obj, in_memory=True)
        image_bytes = downloaded_file.getbuffer().tobytes()
        
        # Call ApyHub API
        res = await remove_background_request(image_bytes)
        if not res["success"]:
            return await msg.edit_text(
                f"❌ **Background Removal Failed** (`{res.get('status', 500)}`):\n`{safe_truncate(res['error'])}`\n\n"
                "_Tip: Ensure your `APYHUB_API_KEY` is configured correctly in `config.py`._",
                parse_mode=ParseMode.MARKDOWN
            )

        # Prepare processed image for return
        output_stream = io.BytesIO(res["content"])
        output_stream.name = "removed_background.png"

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="apy_home")]])

        await message.reply_document(
            document=output_stream,
            caption="✨ **Background successfully removed via ApyHub!**",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ Error processing image:\n`{safe_truncate(str(e))}`", parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^apy_home$"))
async def cb_apy_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "✂️ **ApyHub Image Background Removal Suite**\n\n"
        "Remove backgrounds from photos instantly at scale using multipart API integration.\n\n"
        "👉 **How to use:** Send any photo or image attachment with caption `/removebg` to process it automatically!"
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=get_apyhub_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^apy_guide$"))
async def cb_apy_guide(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="apy_home")]])
    guide_text = (
        "📖 **ApyHub Usage Guide**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "1. Upload any portrait, product photo, or object image to chat.\n"
        "2. Add the caption `/removebg` or reply to the photo with `/removebg`.\n"
        "3. The bot sends back a clean transparent PNG file instantly!\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(safe_truncate(guide_text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^apy_close$"))
async def cb_apy_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
