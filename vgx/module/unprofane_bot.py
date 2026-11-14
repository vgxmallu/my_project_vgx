import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain UNPROFANE_API_KEY

# --- CONFIGURATION & ENDPOINT ---
UNPROFANE_API_URL = "https://api.unprofane.com/v1/check"

def get_unprofane_token() -> str:
    """Retrieves the Unprofane API token from config safely."""
    return getattr(Config, "UNPROFANE_API_KEY", None)


# --- UNPROFANE API HELPER ---

async def check_profanity_via_unprofane(text: str) -> dict:
    """Sends a POST request to Unprofane API to evaluate text content."""
    token = get_unprofane_token()
    if not token:
        return {"error": "Missing UNPROFANE_API_KEY in config.py"}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"text": text.strip()}  # Adjust payload structure per official Unprofane OpenAPI spec if needed

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(UNPROFANE_API_URL, json=payload, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            print(f"Unprofane API HTTP Error [{resp.status_code}]: {resp.text}")
            return {"error": f"API returned status {resp.status_code}"}
        except Exception as e:
            print(f"Unprofane API Exception: {e}")
            return {"error": str(e)}


# --- COMMAND HANDLER ---

@app.on_message(filters.command(["unprofane", "profanity", "checktext"]))
async def cmd_unprofane_check(client: Client, message: Message):
    """Command: /unprofane <text> - Checks text for profanity using Unprofane API."""
    text_input = message.text.partition(" ")[2].strip()
    
    # Allow replying to a message to check its content
    if not text_input and message.reply_to_message:
        text_input = (message.reply_to_message.text or message.reply_to_message.caption or "").strip()

    if not text_input:
        return await message.reply_text(
            "⚠️ **Usage:** `/unprofane <text to check>` (or reply to any message)\n\n"
            "_Example:_ `/unprofane Hello world, this is a clean test.`",
            parse_mode=ParseMode.MARKDOWN
        )

    msg = await message.reply_text("🛡️ Analyzing text via Unprofane API...")

    result = await check_profanity_via_unprofane(text_input)
    if "error" in result:
        return await msg.edit_text(f"❌ **Unprofane Error:** `{result['error']}`", parse_mode=ParseMode.MARKDOWN)

    # Parse standard response attributes (adjust keys based on exact response schema)
    is_profane = result.get("profane", result.get("is_profane", False))
    score = result.get("score", result.get("confidence", 0.0))
    status_badge = "🔴 Contains Profanity / Inappropriate" if is_profane else "🟢 Clean / Safe"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Close", callback_data="unprofane_close")]
    ])

    await msg.edit_text(
        f"🛡️ **Unprofane Analysis Result**\n\n"
        f"• **Status:** {status_badge}\n"
        f"• **Score / Confidence:** `{score}`\n"
        f"• **Checked Text:**\n> `{text_input}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# --- INTERACTIVE CALLBACK ROUTER ---

@app.on_callback_query(filters.regex(r"^unprofane_close$"))
async def cb_unprofane_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
