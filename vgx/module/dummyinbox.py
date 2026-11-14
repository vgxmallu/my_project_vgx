import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# --- CONFIGURATION & ENDPOINT ---
DUMMYINBOX_BASE = "https://dummyinbox.com/api/v1"


async def dub_api_request(method: str, endpoint: str, **kwargs) -> dict:
    """Centralized async HTTP request helper for DummyInbox API."""
    url = f"{DUMMYINBOX_BASE}/{endpoint.lstrip('/')}"
    headers = {"Accept": "application/json"}
    kwargs.setdefault("headers", {}).update(headers)

    async with httpx.AsyncClient(timeout=35.0) as client:
        try:
            if method.upper() == "POST":
                resp = await client.post(url, **kwargs)
            else:
                resp = await client.get(url, **kwargs)

            if resp.status_code in [200, 201]:
                return resp.json()
            print(f"DummyInbox API Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"DummyInbox API Exception [{endpoint}]: {e}")
        return {}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_dub_main_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for DummyInbox."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌐 List Domains", callback_data="dub_domains"),
            InlineKeyboardButton("✨ Create Inbox", callback_data="dub_create")
        ],
        [
            InlineKeyboardButton("📥 Check Messages Guide", callback_data="dub_help_msgs"),
            InlineKeyboardButton("❌ Close", callback_data="dub_close")
        ]
    ])


@app.on_message(filters.command(["dub", "dummyinbox", "tempmail"]))
async def cmd_dub_dashboard(client: Client, message: Message):
    """Command: /dub - Opens the DummyInbox temporary email suite dashboard."""
    text = (
        "📫 **DummyInbox Intelligence Suite**\n\n"
        "Generate throwaway test email addresses, list active domains, and long-poll for incoming verification codes instantly:"
    )
    await message.reply_text(text, reply_markup=get_dub_main_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- 1. LIST DOMAINS ---
# ==========================================

@app.on_message(filters.command(["dubinboxes", "dubdomains"]))
async def cmd_dub_domains(client: Client, message: Message):
    """Command: /dubinboxes - Lists domains you can use for addresses."""
    msg = await message.reply_text("🌐 Fetching available domains...")
    data = await dub_api_request("GET", "domains")
    domains = data.get("domains", [])

    if not domains:
        return await msg.edit_text("❌ Failed to retrieve domains from DummyInbox.")

    domain_list = "\n".join([f"• `{d}`" for d in domains])
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Create Random Address", callback_data="dub_create")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="dub_home")]
    ])

    await msg.edit_text(
        f"🌐 **Available DummyInbox Domains**\n\n{domain_list}",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# ==========================================
# --- 2. CREATE RANDOM ADDRESS ---
# ==========================================

@app.on_message(filters.command(["dubinbox", "dubcreate"]))
async def cmd_dub_create_inbox(client: Client, message: Message):
    """Command: /dubinbox - Generates a new random temporary email address."""
    msg = await message.reply_text("✨ Generating random temporary inbox...")
    data = await dub_api_request("POST", "inboxes")

    address = data.get("address")
    domain = data.get("domain")
    web_url = data.get("webUrl")

    if not address:
        return await msg.edit_text("❌ Failed to generate a new inbox address.")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Open Web Inbox", url=web_url)],
        [InlineKeyboardButton("📥 Check Messages", callback_data=f"dub_check_{address}")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="dub_home")]
    ])

    await msg.edit_text(
        f"✅ **Temporary Inbox Created!**\n\n"
        f"• **Address:** `{address}`\n"
        f"• **Domain:** `{domain}`\n"
        f"• **Web Inbox:** [View Inbox]({web_url})\n\n"
        f"💡 _Tip: Use `/dumessages {address}` to check incoming mail._",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


# ==========================================
# --- 3. LIST & WAIT FOR MESSAGES ---
# ==========================================

@app.on_message(filters.command(["dumessages", "dubcheck"]))
async def cmd_dub_messages(client: Client, message: Message):
    """Command: /dumessages <address> [wait_seconds] - Lists messages or long-polls."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/dumessages <email_address> [wait_seconds]`\n\n"
            "_Example:_ `/dumessages k7m2q9xw4c8rbd3t@dummyinbox.com 30`",
            parse_mode=ParseMode.MARKDOWN
        )

    address = args[1].strip()
    wait_time = int(args[2].strip()) if len(args) > 2 and args[2].isdigit() else 10
    wait_time = min(wait_time, 30)  # Capped at 30 seconds per API limits

    msg = await message.reply_text(f"⏳ Long-polling inbox `{address}` for up to {wait_time}s...")

    # Query parameters for list messages (with wait option)
    params = {"wait": wait_time}
    data = await dub_api_request("GET", f"inboxes/{address}/messages", params=params)

    messages = data.get("messages", [])
    total = data.get("total", 0)

    if not messages:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Poll Again", callback_data=f"dub_check_{address}")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="dub_home")]
        ])
        return await msg.edit_text(
            f"📭 **Inbox Empty:** `{address}`\n"
            f"No messages arrived during the {wait_time}-second wait window.",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    summary_lines = [f"📬 **Inbox Messages for `{address}`** (Total: {total})\n"]
    for idx, mail in enumerate(messages[:5], start=1):
        sender = mail.get("fromName") or mail.get("from", "Unknown")
        subject = mail.get("subject", "No Subject")
        snippet = mail.get("snippet", "No snippet")
        received = mail.get("receivedAt", "")
        att_count = mail.get("attachmentCount", 0)

        summary_lines.append(
            f"**{idx}. From:** `{sender}`\n"
            f"• **Subject:** {subject}\n"
            f"• **Snippet:** _{snippet}_\n"
            f"• **Attachments:** `{att_count}` | ⏱️ `{received}`\n"
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Check Again", callback_data=f"dub_check_{address}")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="dub_home")]
    ])

    await msg.edit_text(
        "\n".join(summary_lines),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^dub_home$"))
async def cb_dub_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "📫 **DummyInbox Intelligence Suite**\n\n"
        "Generate throwaway test email addresses, list active domains, and long-poll for incoming verification codes instantly:"
    )
    await query.message.edit_text(text, reply_markup=get_dub_main_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^dub_domains$"))
async def cb_dub_domains(client: Client, query: CallbackQuery):
    await query.answer("Fetching domains...")
    data = await dub_api_request("GET", "domains")
    domains = data.get("domains", [])
    domain_list = "\n".join([f"• `{d}`" for d in domains])

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Create Random Address", callback_data="dub_create")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="dub_home")]
    ])
    await query.message.edit_text(
        f"🌐 **Available DummyInbox Domains**\n\n{domain_list}",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^dub_create$"))
async def cb_dub_create(client: Client, query: CallbackQuery):
    await query.answer("Generating inbox...")
    data = await dub_api_request("POST", "inboxes")
    address = data.get("address")
    domain = data.get("domain")
    web_url = data.get("webUrl")

    if not address:
        return await query.answer("Failed to create inbox.", show_alert=True)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Open Web Inbox", url=web_url)],
        [InlineKeyboardButton("📥 Check Messages", callback_data=f"dub_check_{address}")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="dub_home")]
    ])
    await query.message.edit_text(
        f"✅ **Temporary Inbox Created!**\n\n"
        f"• **Address:** `{address}`\n"
        f"• **Domain:** `{domain}`\n"
        f"• **Web Inbox:** [View Inbox]({web_url})\n\n"
        f"💡 _Tip: Use `/dumessages {address}` to check incoming mail._",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


@app.on_callback_query(filters.regex(r"^dub_check_(?P<addr>.+)$"))
async def cb_dub_check_inbox(client: Client, query: CallbackQuery):
    address = query.matches[0].group("addr")
    await query.answer(f"Polling {address}...")
    
    # Quick poll with 10s wait
    data = await dub_api_request("GET", f"inboxes/{address}/messages", params={"wait": 10})
    messages = data.get("messages", [])
    total = data.get("total", 0)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Poll Again", callback_data=f"dub_check_{address}")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="dub_home")]
    ])

    if not messages:
        return await query.message.edit_text(
            f"📭 **Inbox Empty:** `{address}`\n"
            f"No messages arrived yet. Click below to poll again.",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    summary_lines = [f"📬 **Inbox Messages for `{address}`** (Total: {total})\n"]
    for idx, mail in enumerate(messages[:5], start=1):
        sender = mail.get("fromName") or mail.get("from", "Unknown")
        subject = mail.get("subject", "No Subject")
        snippet = mail.get("snippet", "No snippet")
        received = mail.get("receivedAt", "")
        summary_lines.append(f"**{idx}. From:** `{sender}`\n• **Subject:** {subject}\n• **Snippet:** _{snippet}_\n")

    await query.message.edit_text(
        "\n".join(summary_lines),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


@app.on_callback_query(filters.regex(r"^dub_help_msgs$"))
async def cb_dub_help_msgs(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="dub_home")]])
    await query.message.edit_text(
        "📥 **How to Check Messages**\n\n"
        "Use the command followed by your temporary email address and optional wait time (up to 30s):\n\n"
        "`/dumessages your_address@dummyinbox.com 30`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^dub_close$"))
async def cb_dub_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
