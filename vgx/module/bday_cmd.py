import pytz
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from vgx.database.bday_db import set_user_bday, get_group, update_group, add_trusted_user

@Client.on_message(filters.command(["setbirthday", "bdayset", "bday"]))
async def set_bdfirthday(client, message):
    args = message.command
    
    # If they use '/bday set DD/MM Timezone' vs '/setbirthday DD/MM Timezone'
    # Let's handle both dynamically:
    date_arg_idx = 2 if len(args) > 1 and args[1].lower() == "set" else 1
    tz_arg_idx = date_arg_idx + 1

    if len(args) <= tz_arg_idx:
        return await message.reply(
            "📝 **Set your Birthday!**\n\n"
            "**Usage:** `/bday [set] DD/MM Timezone`\n"
            "**Example:** `/bday 25/12 Europe/London`\n"
            "*(If you don't know your timezone, use 'UTC')*"
        )
    
    try:
        date_parts = args[date_arg_idx].split("/")
        day, month = int(date_parts[0]), int(date_parts[1])
        timezone = args[tz_arg_idx]
        
        # Validation
        if timezone != "UTC" and timezone not in pytz.all_timezones:
            return await message.reply("❌ Invalid Timezone. Please use a valid IANA timezone (e.g., America/New_York).")
        if not (1 <= month <= 12 and 1 <= day <= 31):
            raise ValueError
            
    except Exception:
        return await message.reply("❌ Invalid format. Please use: `/bday DD/MM Timezone` (e.g., `25/12 UTC`)")

    await set_user_bday(message.from_user.id, month, day, timezone)
    await message.reply(f"✅ **Saved!** Your birthday is set to **{day:02d}/{month:02d}** ({timezone}). We'll remember it!")


# --- Group Admin Helper ---
async def is_admin(client, chat_id, user_id):
    if not user_id: 
        return False # Handles anonymous admins
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except:
        return False


@Client.on_message(filters.command("bdaytoggle") & filters.group)
async def toggle_bday_module(client, message):
    if not message.from_user or not await is_admin(client, message.chat.id, message.from_user.id): 
        return
    s = await get_group(message.chat.id)
    new_state = not s.get("enabled", False)
    await update_group(message.chat.id, enabled=new_state)
    await message.reply(f"✅ Birthday celebrations are now **{'ON' if new_state else 'OFF'}**.")


@Client.on_message(filters.command("bdaymedia") & filters.group)
async def set_bday_media(client, message):
    """Reply to a GIF or Photo with /bdaymedia to set it as the celebration image."""
    if not message.from_user or not await is_admin(client, message.chat.id, message.from_user.id): 
        return
    
    if not message.reply_to_message or not (message.reply_to_message.photo or message.reply_to_message.animation):
        return await message.reply("❌ Please **reply** to a Photo or GIF with `/bdaymedia` to save it.")
        
    media_id = message.reply_to_message.photo.file_id if message.reply_to_message.photo else message.reply_to_message.animation.file_id
    await update_group(message.chat.id, media_id=media_id)
    await message.reply("✅ Celebration media updated successfully!")


@Client.on_message(filters.command("bdaytrust") & filters.group)
async def trust_user(client, message):
    """Adds replied users to a celebration whitelist."""
    if not message.from_user or not await is_admin(client, message.chat.id, message.from_user.id): 
        return
    
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply("❌ Please reply to a user's message to add them to the Trusted List.")
        
    target_user = message.reply_to_message.from_user.id
    await add_trusted_user(message.chat.id, target_user)
    await message.reply("🛡 **Trusted List Updated!** This user will now be celebrated.")
