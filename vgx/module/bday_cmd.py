import pytz
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus

import asyncio
from datetime import datetime

from pyrogram.errors import FloodWait
from vgx import app


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


#================================

async def birthday_worker(app):
    """Hourly background loop optimized to check user timezones efficiently."""
    while True:
        try:
            now_utc = datetime.now(pytz.utc)
            
            # OPTIMIZATION: Instead of scanning 500+ timezones, 
            # query users or group them by their timezone.
            # Assuming you have a function or database query to get all registered users:
            all_users = await get_all_birthday_users() # Replace with your actual DB fetch function
            
            # Dictionary to group users whose local time is currently 8 AM: {tz_name: [user_data, ...]}
            triggered_tzs = {}

            for user_data in all_users:
                tz_name = user_data.get("timezone", "UTC")
                try:
                    tz = pytz.timezone(tz_name)
                    local_time = now_utc.astimezone(tz)
                    
                    # Check if it's 8:00 AM locally
                    if local_time.hour == 8:
                        month, day = local_time.month, local_time.day
                        
                        # Verify it matches their saved birthday month/day
                        if user_data.get("month") == month and user_data.get("day") == day:
                            if tz_name not in triggered_tzs:
                                triggered_tzs[tz_name] = []
                            triggered_tzs[tz_name].append(user_data)
                except Exception:
                    continue

            # Announce for each timezone group found
            for tz_name, users in triggered_tzs.items():
                await announce_birthdays(app, users)

            # Sleep exactly 1 hour before the next global sweep
            await asyncio.sleep(3600)
            
        except Exception as e:
            print(f"Scheduler Error: {e}")
            await asyncio.sleep(60)

async def announce_birthdays(app, users: list):
    """Dispatches messages to groups safely."""
    cursor = groups_col.find({"enabled": True})
    active_groups = await cursor.to_list(length=None)
    
    for group in active_groups:
        chat_id = group["chat_id"]
        
        for user_data in users:
            user_id = user_data["user_id"]
            
            # 🛡 Trusted Role System Check
            if group.get("trusted_only", False):
                if user_id not in group.get("trusted_users", []):
                    continue # Skip if user isn't trusted
            
            try:
                # Get user to tag them
                member = await app.get_chat_member(chat_id, user_id)
                
                # Default message fallback if custom_msg isn't defined in the group doc
                custom_template = group.get("custom_msg", "🎉 Happy Birthday {mention}! Have an amazing day! 🎂")
                msg_text = custom_template.replace("{mention}", member.user.mention)
                
                media_id = group.get("media_id")
                
                # 🛠 Fixed Media Dispatching
                if media_id:
                    try:
                        # Pyrogram send_cached_media takes file_id directly as the first argument
                        await app.send_cached_media(chat_id, file_id=media_id, caption=msg_text)
                    except Exception:
                        # Fallback to plain message if cached media fails (e.g., invalid file_id)
                        await app.send_message(chat_id, text=msg_text)
                else:
                    await app.send_message(chat_id, text=msg_text)
                    
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass # Bot kicked, lacks permissions, or user left the group
