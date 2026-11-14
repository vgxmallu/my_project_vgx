import os
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config 
# --- CONFIGURATION ---
ADELI_BASE_URL = os.getenv("ADELI_URL", "https://app.tryadeli.com/api/v1")


async def adeli_request(method: str, endpoint: str, json_data: dict = None, params: dict = None) -> dict:
    """Helper utility for asynchronous requests to the Adeli API via httpx."""
    headers = {
        "Authorization": f"Bearer {Config.ADELI_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    url = f"{ADELI_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.request(method, url, json=json_data, params=params, headers=headers)
            if response.status_code in [200, 201]:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "status": response.status_code, "error": response.text}
        except Exception as e:
            return {"success": False, "status": 500, "error": str(e)}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_adeli_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for Adeli Social API controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Check Profile (/me)", callback_data="adeli_me"),
            InlineKeyboardButton("🔗 Connected Accounts", callback_data="adeli_accounts")
        ],
        [
            InlineKeyboardButton("🚀 Quickstart Guide", callback_data="adeli_help"),
            InlineKeyboardButton("📚 Adeli Docs", url="https://www.tryadeli.com/docs")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="adeli_close")]
    ])


@app.on_message(filters.command(["adeli", "social", "publisher"]))
async def cmd_adeli_dashboard(client: Client, message: Message):
    """Command: /adeli - Opens the master interactive Adeli Social API dashboard."""
    text = (
        "🌐 **Adeli Unified Social API Suite**\n\n"
        "Manage profiles, check connected accounts, stage media uploads, and cross-publish "
        "to Instagram, TikTok, YouTube, X, and Bluesky from Telegram.\n\n"
        "Select an option below:"
    )
    await message.reply_text(text, reply_markup=get_adeli_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["adelime", "socialme"]))
async def cmd_adeli_me(client: Client, message: Message):
    """Command: /adelime - Fetches organization & profile details for the active API key."""
    msg = await message.reply_text("🔍 Querying Adeli API profile...")
    
    res = await adeli_request("GET", "me")
    if not res["success"]:
        return await msg.edit_text(f"❌ API Request Failed (`{res['status']}`):\n`{res['error']}`", parse_mode=ParseMode.MARKDOWN)

    data = res["data"]
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="adeli_home")]])

    response_text = (
        f"👤 **ADELI ORGANIZATION PROFILE**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Default Profile ID:** `{data.get('profileId', 'N/A')}`\n"
        f"• **Organization:** `{data.get('organizationName', 'N/A')}`\n"
        f"• **Email/User:** `{data.get('email', 'N/A')}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await msg.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["adeliclients", "socialaccounts"]))
async def cmd_adeli_accounts(client: Client, message: Message):
    """Command: /adeliclients - Lists all connected social media accounts."""
    msg = await message.reply_text("📥 Fetching connected social channels...")
    
    res = await adeli_request("GET", "accounts")
    if not res["success"]:
        return await msg.edit_text(f"❌ Failed to fetch accounts (`{res['status']}`):\n`{res['error']}`", parse_mode=ParseMode.MARKDOWN)

    accounts = res["data"].get("accounts", []) if isinstance(res["data"], dict) else res["data"]
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="adeli_home")]])

    if not accounts:
        return await msg.edit_text(
            "📭 **Connected Accounts**\n\nNo social accounts connected yet. Link channels via your Adeli dashboard.",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    acc_list = "\n".join([f"• **{acc.get('platform', 'Unknown')}**: `{acc.get('name', acc.get('accountId'))}`" for acc in accounts[:10]])
    
    response_text = (
        f"🔗 **CONNECTED SOCIAL ACCOUNTS**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{acc_list}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await msg.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^adeli_home$"))
async def cb_adeli_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🌐 **Adeli Unified Social API Suite**\n\n"
        "Manage profiles, check connected accounts, stage media uploads, and cross-publish "
        "to Instagram, TikTok, YouTube, X, and Bluesky from Telegram.\n\n"
        "Select an option below:"
    )
    await query.message.edit_text(text, reply_markup=get_adeli_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^adeli_me$"))
async def cb_adeli_me(client: Client, query: CallbackQuery):
    await query.answer("Fetching profile...")
    res = await adeli_request("GET", "me")
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="adeli_home")]])
    if not res["success"]:
        return await query.message.edit_text(f"❌ Error: `{res['error']}`", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    data = res["data"]
    response_text = (
        f"👤 **ADELI ORGANIZATION PROFILE**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Default Profile ID:** `{data.get('profileId', 'N/A')}`\n"
        f"• **Organization:** `{data.get('organizationName', 'N/A')}`\n"
        f"• **Email/User:** `{data.get('email', 'N/A')}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^adeli_accounts$"))
async def cb_adeli_accounts(client: Client, query: CallbackQuery):
    await query.answer("Fetching accounts...")
    res = await adeli_request("GET", "accounts")
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="adeli_home")]])
    if not res["success"]:
        return await query.message.edit_text(f"❌ Error: `{res['error']}`", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    accounts = res["data"].get("accounts", []) if isinstance(res["data"], dict) else res["data"]
    acc_list = "\n".join([f"• **{acc.get('platform', 'Unknown')}**: `{acc.get('name', acc.get('accountId'))}`" for acc in accounts[:10]]) if accounts else "No connected accounts found."

    response_text = (
        f"🔗 **CONNECTED SOCIAL ACCOUNTS**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{acc_list}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^adeli_help$"))
async def cb_adeli_help(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="adeli_home")]])
    help_text = (
        "🚀 **Adeli Quickstart Workflow**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "1. **Check Key:** `/adelime` verifies your Bearer token and default profile.\n"
        "2. **List Channels:** `/adeliclients` retrieves target account IDs (`instagram`, `tiktok`, `youtube`, etc.).\n"
        "3. **Upload Media:** Use `POST /api/v1/media/uploads` to obtain short-lived S3 upload URLs.\n"
        "4. **Publish:** Use `POST /api/v1/posts` with your `accountId` and media asset to broadcast.\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(help_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^adeli_close$"))
async def cb_adeli_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
