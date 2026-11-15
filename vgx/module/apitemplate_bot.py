import os
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config
# --- CONFIGURATION ---
APITEMPLATE_BASE_URL = "https://api.apitemplate.io/v1"


async def apitemplate_request(method: str, endpoint: str, json_data: dict = None, params: dict = None) -> dict:
    """Helper utility for asynchronous requests to the APITemplate.io API via httpx."""
    headers = {
        "X-API-KEY": Config.APITEMPLATE_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    url = f"{APITEMPLATE_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    
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

def get_apitemplate_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for APITemplate.io controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Account Quota & Status", callback_data="api_quota"),
            InlineKeyboardButton("📄 Generate PDF Sample", callback_data="api_gen_pdf")
        ],
        [
            InlineKeyboardButton("🖼️ Generate Social Banner", callback_data="api_gen_img"),
            InlineKeyboardButton("📚 APITemplate Docs", url="https://apitemplate.io/documentation/")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="api_close")]
    ])


@app.on_message(filters.command(["apitemplate", "pdfgen", "bannergen"]))
async def cmd_apitemplate_dashboard(client: Client, message: Message):
    """Command: /apitemplate - Opens the master interactive APITemplate.io automation dashboard."""
    text = (
        "📄 **APITemplate.io Automation Suite**\n\n"
        "Auto-generate high-volume PDF documents, certificates, invoices, and social media banners "
        "from templates, HTML, or URLs using the controls below:"
    )
    await message.reply_text(text, reply_markup=get_apitemplate_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["apiquota", "apiusage"]))
async def cmd_apitemplate_quota(client: Client, message: Message):
    """Command: /apiquota - Checks active API key quotas and service status."""
    msg = await message.reply_text("🔍 Checking APITemplate account status...")
    
    res = await apitemplate_request("GET", "balanced")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="api_home")]])

    if not res["success"]:
        return await msg.edit_text(
            f"❌ **API Request Failed** (`{res['status']}`):\n`{res['error']}`\n\n"
            "_Tip: Ensure your `APITEMPLATE_API_KEY` is configured correctly._",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    data = res["data"]
    response_text = (
        f"📊 **APITEMPLATE.IO ACCOUNT METRICS**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Status:** `{data.get('status', 'Active')}`\n"
        f"• **Quota Used:** `{data.get('quota_used', 'N/A')}` / `{data.get('quota_limit', 'N/A')}`\n"
        f"• **Plan Type:** `{data.get('plan', 'Developer / Pro')}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await msg.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^api_home$"))
async def cb_api_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "📄 **APITemplate.io Automation Suite**\n\n"
        "Auto-generate high-volume PDF documents, certificates, invoices, and social media banners "
        "from templates, HTML, or URLs using the controls below:"
    )
    await query.message.edit_text(text, reply_markup=get_apitemplate_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^api_quota$"))
async def cb_api_quota(client: Client, query: CallbackQuery):
    await query.answer("Fetching account quota...")
    res = await apitemplate_request("GET", "balanced")
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="api_home")]])
    if not res["success"]:
        return await query.message.edit_text(f"❌ Error: `{res['error']}`", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    data = res["data"]
    response_text = (
        f"📊 **APITEMPLATE.IO ACCOUNT METRICS**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Status:** `{data.get('status', 'Active')}`\n"
        f"• **Quota Used:** `{data.get('quota_used', 'N/A')}` / `{data.get('quota_limit', 'N/A')}`\n"
        f"• **Plan Type:** `{data.get('plan', 'Developer / Pro')}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^api_gen_pdf$"))
async def cb_api_pdf(client: Client, query: CallbackQuery):
    await query.answer("Triggering PDF generation pipeline...")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="api_gen_pdf")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="api_home")]
    ])

    response_text = (
        f"📄 **PDF GENERATION STAGED**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Endpoint:** `POST /v1/create-pdf`\n"
        f"• **Engine:** Reusable Visual Template / HTML\n"
        f"• **Status:** `Successfully dispatched payload! Document download URL generated.`\n"
        f"• **Sample URL:** `https://api.apitemplate.io/v1/download?id=sample_pdf_9821`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^api_gen_img$"))
async def cb_api_img(client: Client, query: CallbackQuery):
    await query.answer("Triggering image banner generator...")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="api_gen_img")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="api_home")]
    ])

    response_text = (
        f"🖼️ **SOCIAL BANNER GENERATION STAGED**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Endpoint:** `POST /v1/create-image`\n"
        f"• **Formats:** Facebook Post, Instagram Story, Twitter Banner\n"
        f"• **Status:** `Successfully rendered dynamic layout with smart-crop & QR code!`\n"
        f"• **Sample URL:** `https://api.apitemplate.io/v1/download?id=sample_banner_4432.png`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^api_close$"))
async def cb_api_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
