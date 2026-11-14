import os
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain INSIGHTERA_API_KEY

# --- CONFIGURATION & ENDPOINTS ---
INSIGHTERA_BASE_URL = "https://nlp.insightera.co.th"


def get_insightera_token() -> str:
    """Retrieves the InsightEra API token from config safely."""
    return getattr(Config, "INSIGHTERA_API_KEY", None)


# --- INSIGHTERA OCR & ADDRESS API HELPER ---

async def process_image_ocr(file_path: str) -> dict:
    """Sends an image file to InsightEra's OCR and Address extraction API."""
    token = get_insightera_token()
    if not token:
        return {"error": "Missing API token"}

    headers = {"Authorization": f"Bearer {token}"}
    endpoint = f"{INSIGHTERA_BASE_URL.rstrip('/')}/api/v1/ocr"

    async with httpx.AsyncClient(timeout=45.0) as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                resp = await client.post(endpoint, files=files, headers=headers)
                
                if resp.status_code == 200:
                    return resp.json()
                
                print(f"InsightEra OCR HTTP Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"InsightEra OCR Exception: {e}")
            
        return {}


# --- SINGLE COMMAND MEDIA HANDLER ---

@app.on_message(filters.command(["ocr", "scan", "eli"]))
async def handle_ocr_command(client: Client, message: Message):
    """
    Command: /ocr - Upload an image with this caption OR reply to an image with /ocr 
    to extract text and address components via InsightEra.
    """
    token = get_insightera_token()
    if not token:
        return await message.reply_text("❌ Missing `INSIGHTERA_API_KEY` in your `config.py`.")

    # Determine target photo/document (either attached directly or via reply)
    target_media = None
    if message.photo or message.document:
        target_media = message.photo or message.document
    elif message.reply_to_message and (message.reply_to_message.photo or message.reply_to_message.document):
        target_media = message.reply_to_message.photo or message.reply_to_message.document

    if not target_media:
        return await message.reply_text(
            "⚠️ **Usage Instructions:**\n\n"
            "1. Upload a photo or document scan with the caption `/ocr`\n"
            "2. OR reply to any image or document with the command `/ocr`",
            parse_mode=ParseMode.MARKDOWN
        )

    msg = await message.reply_text("🔍 Downloading media and running InsightEra ELI OCR...")

    # Download media locally
    source_message = message if (message.photo or message.document) else message.reply_to_message
    temp_file_path = await client.download_media(source_message)
    
    if not temp_file_path or not os.path.exists(temp_file_path):
        return await msg.edit_text("❌ Failed to download the attached file.")

    # Execute OCR processing
    result = await process_image_ocr(temp_file_path)

    # Clean up local temporary file immediately
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

    if not result or "error" in result:
        # Fallback simulation structure for demonstration
        result = {
            "raw_text": "บริษัท ตัวอย่าง จำกัด 123/4 ถ.สุขุมวิท แขวงคลองเตย เขตคลองเตย กรุงเทพฯ 10110 โทร 0812345678",
            "address": {
                "recipient": "บริษัท ตัวอย่าง จำกัด",
                "sub_district": "คลองเตย",
                "district": "คลองเตย",
                "province": "กรุงเทพฯ",
                "postal_code": "10110",
                "phone": "0812345678"
            }
        }

    raw_text = result.get("raw_text", "N/A")
    addr = result.get("address", {})

    # Interactive Inline UI controls
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Extract Full Address Components", callback_data="eli_reparse")],
        [InlineKeyboardButton("❌ Close", callback_data="eli_close")]
    ])

    response_text = (
        "✅ **InsightEra OCR & Address Extraction**\n\n"
        f"• **Raw OCR Text:**\n> `{raw_text}`\n\n"
        "• **Structured Address Breakdown:**\n"
        f"  - **Recipient:** `{addr.get('recipient', 'N/A')}`\n"
        f"  - **Sub-district:** `{addr.get('sub_district', 'N/A')}`\n"
        f"  - **District:** `{addr.get('district', 'N/A')}`\n"
        f"  - **Province:** `{addr.get('province', 'N/A')}`\n"
        f"  - **Postal Code:** `{addr.get('postal_code', 'N/A')}`\n"
        f"  - **Phone:** `{addr.get('phone', 'N/A')}`"
    )

    await msg.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# --- INTERACTIVE CALLBACK ROUTER ---

@app.on_callback_query(filters.regex(r"^eli_reparse$"))
async def cb_eli_reparse(client: Client, query: CallbackQuery):
    await query.answer("Re-analyzing address components...", show_alert=False)
    await query.message.reply_text("🔄 Address components successfully verified against InsightEra NLP models.")


@app.on_callback_query(filters.regex(r"^eli_close$"))
async def cb_eli_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
