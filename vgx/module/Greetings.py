
import os
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from vgx import app


mongo_client = AsyncIOMotorClient(Config.MONGO_URL)
db = mongo_client["GojoBotDB"]
users_col = db["users"]


# --- Helper: Check if User is Banned ---
async def check_banned(client: Client, message: Message):
    user_id = message.from_user.id
    user = await users_col.find_one({"_id": user_id})
    if user and user.get("banned", False):
        await message.reply("❌ You are banned from using this bot.")
        return True
    return False


# ==========================================
# 🟢 1. START COMMAND & USER LOGIN LOGGING
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    if await check_banned(client, message):
        return

    user = message.from_user
    user_id = user.id
    username = f"@{user.username}" if user.username else "No Username"

    # Check if user already exists in MongoDB
    user_doc = await users_col.find_one({"_id": user_id})

    if not user_doc:
        # Register new user
        await users_col.insert_one({
            "_id": user_id,
            "name": user.first_name,
            "username": user.username,
            "banned": False,
            "joined_date": datetime.utcnow()
        })

        # Send log to log channel for new user
        log_text = (
            f"🟢 **New User Started Bot**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Name:** {user.mention}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"🌐 **Username:** {username}"
        )
        await client.send_message(Config.LOG_CHANNEL, log_text)

    # Welcome response to user
    await message.reply_text(
        f"Hi **{user.first_name}**! 👋\n\n"
        f"Welcome to advanced schedule & management bot. You have successfully logged in!"
        f"🍀 @XBOTS_X"
    )


# ==========================================
# 🤖 2. GROUP ADD LOGGING
# ==========================================
@app.on_message(filters.new_chat_members)
async def group_added_handler(client: Client, message: Message):
    for member in message.new_chat_members:
        if member.id == client.me.id:
            chat = message.chat
            adder = message.from_user
            adder_username = f"@{adder.username}" if adder.username else "No Username"

            log_text = (
                f"🤖 **Bot Added to Group**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👥 **Group Name:** {chat.title}\n"
                f"🆔 **Group ID:** `{chat.id}`\n"
                f"💬 **Members Count:** {await client.get_chat_members_count(chat.id)}\n"
                f"👤 **Added By:** {adder.mention} (`{adder.id}` | {adder_username})"
            )
            await client.send_message(Config.LOG_CHANNEL, log_text)


# ==========================================
# 📊 3. STATS COMMAND (Owner Only)
# ==========================================
@app.on_message(filters.command("stats") & filters.user(Config.ADMIN_ID))
async def stats_handler(client: Client, message: Message):
    total_users = await users_col.count_documents({})
    banned_users = await users_col.count_documents({"banned": True})
    active_users = total_users - banned_users

    stats_text = (
        f"📊 **Bot Statistics Dashboard**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👥 **Total Started Users:** `{total_users}`\n"
        f"🟢 **Active Users:** `{active_users}`\n"
        f"🔴 **Banned Users:** `{banned_users}`"
    )
    await message.reply_text(stats_text)


# ==========================================
# 📢 4. BROADCAST COMMAND (Owner Only)
# ==========================================
@app.on_message(filters.command("broadcast") & filters.user(Config.ADMIN_ID))
async def broadcast_handler(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Please reply to a message to broadcast it to all users.")

    status_msg = await message.reply_text("📢 Broadcast in progress...")
    
    total = await users_col.count_documents({"banned": {"$ne": True}})
    sent = 0
    failed = 0

    async for user in users_col.find({"banned": {"$ne": True}}):
        user_id = user["_id"]
        try:
            await message.reply_to_message.copy(chat_id=user_id)
            sent += 1
            await asyncio.sleep(0.05)  # Prevent FloodWait
        except Exception:
            failed = failed + 1

    await status_msg.edit_text(
        f"✅ **Broadcast Completed!**\n\n"
        f"📤 **Successfully Sent:** `{sent}`\n"
        f"⚠️ **Failed / Blocked:** `{failed}`"
    )


# ==========================================
# 🚫 5. BAN & UNBAN COMMANDS (Owner Only)
# ==========================================
@app.on_message(filters.command("ban") & filters.user(Config.ADMIN_ID))
async def ban_user_handler(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/ban <user_id>`")
    
    try:
        target_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Invalid User ID format.")

    result = await users_col.update_one({"_id": target_id}, {"$set": {"banned": True}})
    
    if result.modified_count > 0 or result.upserted_id:
        await message.reply_text(f"✅ User `{target_id}` has been **banned** from the bot.")
    else:
        # If user isn't in DB yet, force create entry as banned
        await users_col.update_one({"_id": target_id}, {"$set": {"banned": True}}, upsert=True)
        await message.reply_text(f"✅ User `{target_id}` was not found in database, but marked as **banned**.")


@app.on_message(filters.command("unban") & filters.user(Config.ADMIN_ID))
async def unban_user_handler(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/unban <user_id>`")
    
    try:
        target_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Invalid User ID format.")

    result = await users_col.update_one({"_id": target_id}, {"$set": {"banned": False}})
    
    if result.modified_count > 0:
        await message.reply_text(f"✅ User `{target_id}` has been **unbanned**.")
    else:
        await message.reply_text(f"⚠️ User `{target_id}` was not found or was already unbanned.")


