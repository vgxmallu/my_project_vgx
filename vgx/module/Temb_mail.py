import aiohttp
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.temb_db import db
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


API_BASE = "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"

async def generate_email() -> tuple:
    """Generates a random temp email and returns (email, login, domain)."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}?action=genRandomMailbox&count=1") as resp:
            data = await resp.json()
            email = data[0]
            login, domain = email.split("@")
            return email, login, domain

async def check_inbox(login: str, domain: str) -> list:
    """Fetches the latest messages for the given mailbox."""
    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE}?action=getMessages&login={login}&domain={domain}"
        async with session.get(url) as resp:
            return await resp.json()
          
#====================================================

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Generate", callback_data="generate"),
            InlineKeyboardButton("Refresh", callback_data="refresh"),
            InlineKeyboardButton("Stop", callback_data="stop")
        ],
        [
            InlineKeyboardButton("Delete", callback_data="delete"),
            InlineKeyboardButton("Invites", callback_data="invites")
        ]
    ])

@Client.on_message(filters.command("tmail") & filters.private)
async def staznnzcommand(client: Client, message: Message):
    text = (
        "Welcome to Temp Mail Bot! 🚀\n\n"
        "Generate disposable emails and receive messages directly here.\n\n"
        "Click below to generate a temporary email: 📬"
    )
    await message.reply_text(
        text,
        reply_markup=get_main_keyboard()
    )

#====================================================

@Client.on_callback_query(filters.regex(r"^generate$"))
async def cb_generate(client: Client, query: CallbackQuery):
    await query.answer("Generating new email...")
    
    email, login, domain = await generate_email()
    user_id = query.from_user.id
    
    # Store active email state for the user
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"active_email": email, "login": login, "domain": domain}},
        upsert=True
    )
    
    # Log to total collection
    await db.history.insert_one({"user_id": user_id, "email": email})
    
    text = (
        f"✅ **Your Temporary Email:**\n`{email}`\n\n"
        "Waiting for incoming messages..."
    )
    await query.edit_message_text(text, reply_markup=get_main_keyboard())


@Client.on_callback_query(filters.regex(r"^refresh$"))
async def cb_refresh(client: Client, query: CallbackQuery):
    user_data = await db.users.find_one({"_id": query.from_user.id})
    
    if not user_data or "login" not in user_data:
        return await query.answer("No active email. Generate one first!", show_alert=True)
    
    await query.answer("Checking inbox...")
    emails = await check_inbox(user_data["login"], user_data["domain"])
    
    if not emails:
        text = f"✅ **Your Temporary Email:**\n`{user_data['active_email']}`\n\n📭 Inbox is empty."
        # Only edit if the text is different to prevent Pyrogram MessageNotModified errors
        if query.message.text != text:
            await query.edit_message_text(text, reply_markup=get_main_keyboard())
    else:
        text = f"✅ **Your Temporary Email:**\n`{user_data['active_email']}`\n\n📬 **New Messages:**\n"
        for msg in emails[:5]: # Show top 5
            text += f"\n**From:** `{msg['from']}`\n**Subject:** {msg['subject']}\n"
        
        await query.edit_message_text(text, reply_markup=get_main_keyboard())


@Client.on_callback_query(filters.regex(r"^(stop|delete|invites)$"))
async def cb_placeholders(client: Client, query: CallbackQuery):
    # Extracts the exact callback string using the regex match
    action = query.matches[0].group(1)
    
    if action == "delete":
        await db.users.delete_one({"_id": query.from_user.id})
        await query.answer("Active email deleted.", show_alert=True)
        await query.edit_message_text(
            "Welcome to Temp Mail Bot! 🚀\n\n"
            "Generate disposable emails and receive messages directly here.\n\n"
            "Click below to generate a temporary email: 📬",
            reply_markup=get_main_keyboard()
        )
    elif action == "stop":
        await query.answer("Mailbox monitoring stopped.", show_alert=True)
    elif action == "invites":
        await query.answer("Referral system coming soon!", show_alert=True)


@Client.on_message(filters.command("stats") & filters.private)
async def stats_command(client: Client, message: Message):
    # Send a quick loading message
    msg = await message.reply_text("📊 Fetching database statistics...")
    
    # Count the total number of documents in the history collection
    total_emails_generated = await db.history.count_documents({})
    
    # (Optional) Count how many unique users have an active email right now
    active_users = await db.users.count_documents({})
    
    text = (
        "📈 **Temp Mail Bot Statistics**\n\n"
        f"✉️ **Total Emails Generated:** `{total_emails_generated}`\n"
        f"👥 **Current Active Users:** `{active_users}`"
    )
    
    await msg.edit_message_text(text)
