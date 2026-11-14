import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain LINKLY_API_KEY and LINKLY_WORKSPACE_ID

# --- CONFIGURATION & ENDPOINTS ---
LINKLY_API_URL = "https://app.linklyhq.com/api/v1/link"

def get_linkly_config() -> tuple:
    """Retrieves Linkly API Key and Workspace ID from config safely."""
    api_key = getattr(Config, "LINKLY_API_KEY", None) 
    workspace_id = getattr(Config, "LINKLY_WORKSPACE_ID", 1)  # Default workspace ID to 1 if not specified
    return api_key, workspace_id


# --- LINKLY API HELPER ---

async def shorten_url_via_linkly(long_url: str, link_name: str = None) -> dict:
    """Sends a POST request to Linkly API to create a short link."""
    api_key, workspace_id = get_linkly_config()
    if not api_key:
        return {"error": "Missing Linkly API Key"}

    headers = {"Cache-Control": "no-cache"}
    payload = {
        "api_key": api_key,
        "workspace_id": workspace_id,
        "url": long_url.strip()
    }
    if link_name:
        payload["name"] = link_name.strip()

    async with httpx.AsyncClient() as client:
        try:
            # Linkly accepts form-urlencoded or json payloads for link creation
            resp = await client.post(LINKLY_API_URL, data=payload, headers=headers, timeout=15.0)
            if resp.status_code in [200, 201]:
                return resp.json()
            print(f"Linkly API Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Linkly API Exception: {e}")
        return {}


# --- COMMAND HANDLER ---

@app.on_message(filters.command(["linkly", "linklyshort", "ll"]))
async def cmd_linkly_shorten(client: Client, message: Message):
    """Command: /linkly <url> [link_name] - Shortens a long URL using Linkly."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/linkly <long_url> [link_name]`\n\n"
            "_Example:_ `/linkly https://example.com My Awesome Link`",
            parse_mode=ParseMode.MARKDOWN
        )

    long_url = args[1].strip()
    link_name = " ".join(args[2:]) if len(args) > 2 else "Telegram Generated Link"

    if not long_url.startswith(("http://", "https://")):
        long_url = "https://" + long_url

    msg = await message.reply_text("🔗 Generating short link via Linkly...")

    result = await shorten_url_via_linkly(long_url, link_name=link_name)
    if not result or "error" in result or "id" not in result:
        return await msg.edit_text(
            "❌ Failed to create short link.\n\n"
            "💡 **Check your config:** Ensure `LINKLY_API_KEY` and `LINKLY_WORKSPACE_ID` are properly set in `config.py`."
        )

    # Extract fields from Linkly response
    link_id = result.get("id")
    full_url = result.get("full_url") or result.get("url")
    name = result.get("name", link_name)

    # Fallback if full_url isn't directly keyed in the json response object
    if not full_url:
        full_url = long_url  # fallback display

    # Inline Keyboard action buttons
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Open Short Link", url=full_url)],
        [InlineKeyboardButton("❌ Close", callback_data="linkly_close")]
    ])

    response_text = (
        f"✅ **Linkly Short Link Created!**\n\n"
        f"• **Name:** `{name}`\n"
        f"• **ID:** `{link_id}`\n"
        f"• **Original:** `{long_url}`\n"
        f"• **Shortened:** `{full_url}`"
    )

    await msg.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# --- INTERACTIVE CALLBACK ROUTER ---

@app.on_callback_query(filters.regex(r"^linkly_close$"))
async def cb_linkly_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
