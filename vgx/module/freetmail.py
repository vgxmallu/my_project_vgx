import os
import random
import string
from datetime import datetime, timezone
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.errors import MessageNotModified
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from vgx import app

# ==========================================
# ⚙️ CONFIG & MONGODB SETUP
# ==========================================
FCE_API_KEY = getattr(Config, "FCE_API_KEY", None) 
FCE_BASE_URL = "https://api2.freecustom.email/v1"

MONGO_URL = getattr(Config, "MONGO_URL", None)
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client[getattr(Config, "DB_NAME")]

fmails_col = db["freecustom_mails"]          # Stores each generated temp email
fmail_users_col = db["freecustom_users"]    # Stores per-user stats & active mail


# ==========================================
# 🌐 FREECUSTOM.EMAIL API CLIENT
# ==========================================
async def fce_request(method: str, path: str, json_body: dict = None):
    headers = {
        "Authorization": f"Bearer {FCE_API_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{FCE_BASE_URL}{path}"
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.request(method, url, headers=headers, json=json_body) as resp:
            try:
                data = await resp.json()
            except Exception:
                data = {"raw": await resp.text()}
            return resp.status, data


async def get_available_domains():
    status, data = await fce_request("GET", "/domains")
    if status == 200 and isinstance(data, dict):
        domains = data.get("data") or data.get("domains") or []
        parsed = []
        for item in domains:
            if isinstance(item, str):
                parsed.append(item)
            elif isinstance(item, dict) and item.get("domain"):
                parsed.append(item["domain"])
        if parsed:
            return parsed
    # Fallback default platform domains if endpoint returns an empty/different shape
    return ["ditapi.info", "ditube.info"]


async def create_temp_inbox(custom_prefix: str = None):
    domains = await get_available_domains()
    domain = random.choice(domains)
    rand_tag = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    prefix = custom_prefix.lower() if custom_prefix else f"vgx_{rand_tag}"
    inbox_addr = f"{prefix}@{domain}"

    status, data = await fce_request("POST", "/inboxes", json_body={"inbox": inbox_addr})
    if status in (200, 201):
        registered_addr = data.get("inbox") or data.get("data", {}).get("inbox") or inbox_addr
        return True, registered_addr, None
    err = data.get("message") or data.get("error") or f"HTTP {status}"
    return False, None, str(err)


async def fetch_inbox_messages(inbox_addr: str):
    status, data = await fce_request("GET", f"/inboxes/{inbox_addr}/messages")
    if status == 200 and isinstance(data, dict):
        msgs = data.get("data") or data.get("messages") or []
        return True, msgs, None
    err = data.get("message") or data.get("error") or f"HTTP {status}"
    return False, [], str(err)


async def fetch_latest_otp(inbox_addr: str):
    status, data = await fce_request("GET", f"/inboxes/{inbox_addr}/otp")
    if status == 200 and isinstance(data, dict):
        payload = data.get("data") if isinstance(data.get("data"), dict) else data
        otp = payload.get("otp") or payload.get("code")
        link = payload.get("link") or payload.get("verification_link")
        return True, otp, link, None
    err = data.get("message") or data.get("error") or f"HTTP {status}"
    return False, None, None, str(err)


async def delete_remote_inbox(inbox_addr: str):
    status, _ = await fce_request("DELETE", f"/inboxes/{inbox_addr}")
    return status in (200, 204)


# ==========================================
# 🗄️ MONGODB HELPERS
# ==========================================
async def record_generated_fmail(user_id: int, username: str, email_addr: str):
    now = datetime.now(timezone.utc)
    await fmails_col.update_one(
        {"email": email_addr},
        {
            "$setOnInsert": {
                "email": email_addr,
                "user_id": user_id,
                "username": username or "",
                "created_at": now,
            },
            "$set": {"last_used_at": now, "active": True},
        },
        upsert=True,
    )
    await fmail_users_col.update_one(
        {"_id": user_id},
        {
            "$set": {"username": username or "", "active_email": email_addr, "updated_at": now},
            "$inc": {"total_fmails": 1},
        },
        upsert=True,
    )


async def get_fmail_stats(user_id: int):
    total_all_fmails = await fmails_col.count_documents({})
    active_fmails = await fmails_col.count_documents({"active": True})
    user_doc = await fmail_users_col.find_one({"_id": user_id}) or {}
    user_count = await fmails_col.count_documents({"user_id": user_id})
    return {
        "total_all": total_all_fmails,
        "active_all": active_fmails,
        "user_count": max(user_count, user_doc.get("total_fmails", 0)),
        "active_email": user_doc.get("active_email"),
    }


# ==========================================
# 🎨 UI KEYBOARDS & RENDERERS (CALLBACK ONLY)
# ==========================================
def build_fmail_keyboard(uid: int, has_email: bool = False):
    rows = [
        [
            InlineKeyboardButton("✨ Generate New Mail", callback_data=f"fce_gen_{uid}"),
            InlineKeyboardButton("📥 Check Inbox", callback_data=f"fce_inbox_{uid}"),
        ],
        [
            InlineKeyboardButton("🔐 Get Latest OTP", callback_data=f"fce_otp_{uid}"),
            InlineKeyboardButton("📂 My Saved Mails", callback_data=f"fce_list_{uid}"),
        ],
        [
            InlineKeyboardButton("📊 DB Mail Stats", callback_data=f"fce_stats_{uid}"),
        ],
    ]
    if has_email:
        rows.append([
            InlineKeyboardButton("🗑 Delete Mail", callback_data=f"fce_del_{uid}"),
        ])
    rows.append([
        InlineKeyboardButton("✖️ Close Panel", callback_data=f"fce_close_{uid}"),
    ])
    return InlineKeyboardMarkup(rows)


async def render_dashboard_text(user_id: int, note: str = ""):
    stats = await get_fmail_stats(user_id)
    active_mail = stats["active_email"] or "None generated yet"
    header = (
        "📨 **FreeCustom Temp Mail Hub**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📧 **Active Mail:** `{active_mail}`\n"
        f"👤 **Your Generated Mails:** `{stats['user_count']}`\n"
        f"🌐 **Total Mails in DB:** `{stats['total_all']}` (`{stats['active_all']}` active)\n"
    )
    if note:
        header += f"\n{note}\n"
    return header


# ==========================================
# ⚡ SIMPLE COMMANDS
# ==========================================
@app.on_message(filters.command(["fmail", "tempmail"]))
async def cmd_fmail(client: Client, message: Message):
    if not FCE_API_KEY:
        return await message.reply_text("❌ `FCE_API_KEY` is not configured in environment/config.")
    uid = message.from_user.id
    stats = await get_fmail_stats(uid)
    text = await render_dashboard_text(uid, "Tap a button below to generate a temp email or read incoming mail.")
    await message.reply_text(text, reply_markup=build_fmail_keyboard(uid, bool(stats["active_email"])))


@app.on_message(filters.command("myfmails"))
async def cmd_myfmails(client: Client, message: Message):
    uid = message.from_user.id
    cursor = fmails_col.find({"user_id": uid}).sort("created_at", -1).limit(10)
    docs = [doc async for doc in cursor]
    if not docs:
        return await message.reply_text("📭 You haven't generated any temp emails yet. Use `/fmail` to create one.")

    lines = ["📂 **Your Saved Temp Mails (Last 10)**\n━━━━━━━━━━━━━━━━━━━━"]
    for idx, doc in enumerate(docs, 1):
        status_icon = "🟢" if doc.get("active", True) else "⚪"
        lines.append(f"{idx}. {status_icon} `{doc['email']}`")

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✨ Generate New Mail", callback_data=f"fce_gen_{uid}"),
            InlineKeyboardButton("📥 Check Active Inbox", callback_data=f"fce_inbox_{uid}"),
        ],
        [InlineKeyboardButton("✖️ Close Panel", callback_data=f"fce_close_{uid}")],
    ])
    await message.reply_text("\n".join(lines), reply_markup=kb)


@app.on_message(filters.command("fmailstats"))
async def cmd_fmailstats(client: Client, message: Message):
    uid = message.from_user.id
    stats = await get_fmail_stats(uid)
    text = (
        "📊 **Temp Mail Database Stats**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 **Total F-Mails Collected in DB:** `{stats['total_all']}`\n"
        f"🟢 **Currently Active F-Mails:** `{stats['active_all']}`\n"
        f"👤 **Your F-Mails Count:** `{stats['user_count']}`"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Generate New Mail", callback_data=f"fce_gen_{uid}")],
        [InlineKeyboardButton("✖️ Close Panel", callback_data=f"fce_close_{uid}")],
    ])
    await message.reply_text(text, reply_markup=kb)


@app.on_message(filters.command("checkmail"))
async def cmd_checkmail(client: Client, message: Message):
    uid = message.from_user.id
    stats = await get_fmail_stats(uid)
    active_mail = stats["active_email"]
    if not active_mail:
        return await message.reply_text("❌ No active temp email found. Use `/fmail` to generate one first.")

    ok, msgs, err = await fetch_inbox_messages(active_mail)
    if not ok:
        return await message.reply_text(f"❌ Failed to fetch inbox: `{err}`")

    if not msgs:
        return await message.reply_text(f"📭 **Inbox Empty:** `{active_mail}`\nNo messages received yet.")

    lines = [f"📥 **Inbox for `{active_mail}`** ({len(msgs)} found)\n━━━━━━━━━━━━━━━━━━━━"]
    for m in msgs[:5]:
        sender = m.get("from") or m.get("sender") or "Unknown"
        subject = m.get("subject") or "(No Subject)"
        lines.append(f"• **From:** `{sender}`\n  **Sub:** {subject}")

    await message.reply_text("\n".join(lines))


# ==========================================
# 🎛️ CALLBACK ROUTER (INLINE BUTTONS ONLY)
# ==========================================
@app.on_callback_query(filters.regex(r"^fce_(gen|inbox|otp|list|stats|del|close)_(\d+)$"))
async def fce_callback_router(client: Client, query: CallbackQuery):
    action = query.matches[0].group(1)
    owner_uid = int(query.matches[0].group(2))

    if query.from_user.id != owner_uid:
        return await query.answer("❌ This panel belongs to another user.", show_alert=True)

    if action == "close":
        try:
            await query.message.delete()
        except Exception:
            await query.message.edit_text("✖️ Panel closed.")
        return await query.answer()

    if action == "gen":
        await query.answer("⏳ Generating inbox...", show_alert=False)
        ok, email_addr, err = await create_temp_inbox()
        if not ok:
            text = await render_dashboard_text(owner_uid, f"❌ **Error:** `{err}`")
            try:
                await query.message.edit_text(text, reply_markup=build_fmail_keyboard(owner_uid, False))
            except MessageNotModified:
                pass
            return

        await record_generated_fmail(owner_uid, query.from_user.username, email_addr)
        text = await render_dashboard_text(owner_uid, f"✅ **New Mail Ready:** `{email_addr}`")
        try:
            await query.message.edit_text(text, reply_markup=build_fmail_keyboard(owner_uid, True))
        except MessageNotModified:
            pass

    elif action == "inbox":
        stats = await get_fmail_stats(owner_uid)
        active_mail = stats["active_email"]
        if not active_mail:
            return await query.answer("⚠️ Generate a temp email first!", show_alert=True)

        await query.answer("📥 Checking inbox...", show_alert=False)
        ok, msgs, err = await fetch_inbox_messages(active_mail)
        if not ok:
            note = f"❌ **Inbox Error:** `{err}`"
        elif not msgs:
            note = f"📭 **No emails yet** in `{active_mail}`."
        else:
            preview = []
            for m in msgs[:4]:
                sender = m.get("from") or m.get("sender") or "Unknown"
                subj = m.get("subject") or "(No Subject)"
                preview.append(f"• `{sender}` — **{subj}**")
            note = f"📥 **Messages ({len(msgs)}):**\n" + "\n".join(preview)

        text = await render_dashboard_text(owner_uid, note)
        try:
            await query.message.edit_text(text, reply_markup=build_fmail_keyboard(owner_uid, True))
        except MessageNotModified:
            pass

    elif action == "otp":
        stats = await get_fmail_stats(owner_uid)
        active_mail = stats["active_email"]
        if not active_mail:
            return await query.answer("⚠️ Generate a temp email first!", show_alert=True)

        await query.answer("🔐 Extracting latest OTP...", show_alert=False)
        ok, otp, link, err = await fetch_latest_otp(active_mail)
        if not ok:
            note = f"❌ **OTP Lookup Failed:** `{err}`"
        else:
            parts = []
            if otp:
                parts.append(f"🔑 **OTP Code:** `{otp}`")
            if link:
                parts.append(f"🔗 **Link:** `{link}`")
            note = "\n".join(parts) if parts else "⏳ No OTP or link found in recent messages yet."

        text = await render_dashboard_text(owner_uid, note)
        try:
            await query.message.edit_text(text, reply_markup=build_fmail_keyboard(owner_uid, True))
        except MessageNotModified:
            pass

    elif action == "list":
        cursor = fmails_col.find({"user_id": owner_uid}).sort("created_at", -1).limit(8)
        docs = [doc async for doc in cursor]
        if not docs:
            return await query.answer("📭 No saved mails in DB yet.", show_alert=True)

        lines = ["📂 **Your Recent Mails in DB:**"]
        for d in docs:
            lines.append(f"• `{d['email']}`")

        text = await render_dashboard_text(owner_uid, "\n".join(lines))
        try:
            await query.message.edit_text(text, reply_markup=build_fmail_keyboard(owner_uid, True))
        except MessageNotModified:
            pass
        await query.answer()

    elif action == "stats":
        stats = await get_fmail_stats(owner_uid)
        note = (
            "📊 **Database Summary:**\n"
            f"• Total F-Mails Stored: `{stats['total_all']}`\n"
            f"• Active F-Mails: `{stats['active_all']}`\n"
            f"• Your F-Mails: `{stats['user_count']}`"
        )
        text = await render_dashboard_text(owner_uid, note)
        try:
            await query.message.edit_text(text, reply_markup=build_fmail_keyboard(owner_uid, bool(stats["active_email"])))
        except MessageNotModified:
            pass
        await query.answer()

    elif action == "del":
        stats = await get_fmail_stats(owner_uid)
        active_mail = stats["active_email"]
        if not active_mail:
            return await query.answer("⚠️ No active mail to delete.", show_alert=True)

        await delete_remote_inbox(active_mail)
        await fmails_col.update_one({"email": active_mail}, {"$set": {"active": False}})
        await fmail_users_col.update_one({"_id": owner_uid}, {"$set": {"active_email": None}})

        text = await render_dashboard_text(owner_uid, f"🗑 **Removed:** `{active_mail}`")
        try:
            await query.message.edit_text(text, reply_markup=build_fmail_keyboard(owner_uid, False))
        except MessageNotModified:
            pass
        await query.answer("Mail deleted!", show_alert=True)
