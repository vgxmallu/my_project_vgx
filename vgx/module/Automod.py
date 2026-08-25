from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.automod_db import get_warn_settings, update_warn_settings, remove_user_warn, get_all_enabled_groups, pop_weekly_stats, add_user_warn, reset_user_warns, increment_stat

#lol
from pyrogram.types import ChatPermissions
from pyrogram.enums import ChatMemberStatus

import asyncio
from datetime import datetime 
import time
from collections import defaultdict, deque
#from pyrogram import Client, filters
from pyrogram.types import ChatPermissions



"""
HELP_PAGES = {
    "home": (
        "🛡 **Advanced Auto-Mod & Warn System**\n\n"
        "Welcome to the control center! I am designed to automatically stop spammers, "
        "manage warnings, and execute punishments fairly.\n\n"
        "👇 **Select a category below to see how I work:**"
    ),
    "setup": (
        "⚙️ **System Setup & Dashboard**\n\n"
        "To configure the bot for a specific group, use the target command in my private messages:\n\n"
        "🔹 `/warntarget <chat_id>` - Opens the visual control panel.\n\n"
        "**From the dashboard, you can:**\n"
        "• Turn the Auto-Mod ON or OFF.\n"
        "• Set the max number of warnings (2 to 6).\n"
        "• Set the final punishment (`Off`, `Kick`, `Mute`, or `Ban`)."
    ),
    "flood": (
        "🌊 **The Auto-Flood Engine**\n\n"
        "The bot runs a high-speed RAM cache to catch spammers instantly.\n\n"
        "• **The Trigger:** If a user sends **7 messages in 10 seconds**, the bot deletes all 7 messages instantly.\n"
        "• **The Action:** It adds 1 Warning to their database profile.\n"
        "• **The Punishment:** If they reach the max warnings allowed by the group, the bot automatically executes the chosen punishment (e.g., Mute for 1 hour)."
    ),
    "cmds": (
        "⚖️ **Admin Commands**\n\n"
        "Admins can manually intervene to forgive users and fix mistakes.\n\n"
        "🔹 `/unwarn` *(Reply to a message)* - Removes 1 warning from that user.\n"
        "🔹 `/unwarn <user_id>` - Removes 1 warning using their ID.\n\n"
        "✨ *Bonus: Using `/unwarn` will also automatically UNMUTE the user and fully restore their chat permissions!*"
    ),
    "audit": (
        "📊 **Weekly Audit Report**\n\n"
        "You don't need to guess if the bot is working. Every single action is tracked in MongoDB.\n\n"
        "Every **Sunday at 8:00 PM**, the bot will automatically compile the stats and send a "
        "beautiful Weekly Report to the group showing exactly how many messages were deleted, users muted, and warns issued."
"""

def build_warn_keyboard(chat_id: int, s: dict):
    # Determine which checkmarks to show
    p_off = "✖️ Off ✅" if s["punishment"] == "off" else "✖️ Off"
    p_kick = "❗️ Kick ✅" if s["punishment"] == "kick" else "❗️ Kick"
    p_mute = "🔇 Mute ✅" if s["punishment"] == "mute" else "🔇 Mute"
    p_ban = "🚫 Ban ✅" if s["punishment"] == "ban" else "🚫 Ban"
    
    # Build the Max Warns row dynamically
    warn_row = []
    for i in range(2, 7):
        text = f"{i} ✅" if s["max_warns"] == i else str(i)
        warn_row.append(InlineKeyboardButton(text, callback_data=f"w_max_{i}_{chat_id}"))

    en_btn = "🟢 Module: ENABLED" if s["enabled"] else "🔴 Module: DISABLED"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(en_btn, callback_data=f"w_tgl_{chat_id}")],
        [InlineKeyboardButton("📄 Warned List", callback_data=f"w_list_{chat_id}")],
        [
            InlineKeyboardButton(p_off, callback_data=f"w_pun_off_{chat_id}"),
            InlineKeyboardButton(p_kick, callback_data=f"w_pun_kick_{chat_id}")
        ],
        [
            InlineKeyboardButton(p_mute, callback_data=f"w_pun_mute_{chat_id}"),
            InlineKeyboardButton(p_ban, callback_data=f"w_pun_ban_{chat_id}")
        ],
        warn_row
    ])

@Client.on_message(filters.command("warntarget") & filters.private)
async def target_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/warntarget -100123456789`")
        
    try:
        chat_id = int(message.command[1])
        s = await get_warn_settings(chat_id)
        
        text = (
            "❗️ **User warnings**\n"
            "The warning system allows you to give warnings to users for incorrect behavior "
            "in the group, before actually punishing them.\n\n"
            "From this menu you can set:\n"
            "• the punishment for users who exceed the maximum of warnings allowed\n"
            "• the maximum number of warns allowed\n\n"
            f"**Punishment:** {s['punishment'].title()}\n"
            f"**Max Warns allowed:** {s['max_warns']}\n"
            f"**Target Chat:** `{chat_id}`"
        )
        
        await message.reply(text, reply_markup=build_warn_keyboard(chat_id, s))
    except ValueError:
        await message.reply("❌ Please provide a valid numeric Group ID.")

# Regex router for the UI actions
@Client.on_callback_query(filters.regex(r"^w_(?P<action>tgl|list|pun_off|pun_kick|pun_mute|pun_ban|max)_(?P<val>[a-z0-9_]+)?_?(?P<chat_id>-?\d+)$"))
async def warn_ui_callbacks(client, query):
    action = query.matches[0].group("action")
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_warn_settings(chat_id)
    
    if action == "tgl":
        await update_warn_settings(chat_id, enabled=not s["enabled"])
    elif action == "list":
        return await query.answer("This would display a list of warned users!", show_alert=True)
    elif action.startswith("pun_"):
        punishment_type = action.split("_")[1]
        await update_warn_settings(chat_id, punishment=punishment_type)
    elif action == "max":
        val = int(query.matches[0].group("val"))
        await update_warn_settings(chat_id, max_warns=val)

    # Refresh the UI with the new database data
    s = await get_warn_settings(chat_id)
    text = (
        "❗️ **User warnings**\n"
        "The warning system allows you to give warnings to users for incorrect behavior "
        "in the group, before actually punishing them.\n\n"
        "From this menu you can set:\n"
        "• the punishment for users who exceed the maximum of warnings allowed\n"
        "• the maximum number of warns allowed\n\n"
        f"**Punishment:** {s['punishment'].title()}\n"
        f"**Max Warns allowed:** {s['max_warns']}\n"
        f"**Target Chat:** `{chat_id}`"
    )
    await query.message.edit_text(text, reply_markup=build_warn_keyboard(chat_id, s))

#=================


async def is_admin(client, chat_id: int, user_id: int) -> bool:
    """Security check to make sure normal users can't unwarn people."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except Exception:
        return False

@Client.on_message(filters.command("unwarn") & filters.group)
async def unwarn_cmd(client, message):
    chat_id = message.chat.id
    admin_id = message.from_user.id
    
    # 1. Security Check: Only Admins!
    if not await is_admin(client, chat_id, admin_id):
        return await message.reply("❌ **Access Denied:** Only admins can unwarn users.")

    # 2. Extract the Target User ID
    target_user_id = None
    target_mention = ""
    
    # Did they reply to a user?
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        target_mention = message.reply_to_message.from_user.mention
    # Did they provide an ID? (e.g., /unwarn 123456789)
    elif len(message.command) > 1:
        try:
            target_user_id = int(message.command[1])
            target_mention = f"User `{target_user_id}`"
        except ValueError:
            return await message.reply("❌ Please provide a valid numeric User ID.")
    else:
        return await message.reply("❌ **Usage:** Reply to a user's message with `/unwarn` or type `/unwarn <user_id>`")

    if not target_user_id:
        return

    # 3. Remove 1 Warning from the MongoDB Database
    remaining_warns = await remove_user_warn(chat_id, target_user_id)
    
    # 4. Unmute the User (Restore their Chat Permissions)
    try:
        await client.restrict_chat_member(
            chat_id,
            target_user_id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        unmute_text = "\n🔊 **Chat permissions restored! (Unmuted)**"
    except Exception:
        # If the bot lacks permissions, it will fail silently without crashing.
        unmute_text = ""
        
    # 5. Send the Success Announcement
    if remaining_warns > 0:
        await message.reply(
            f"✅ **Warning Removed!**\n"
            f"{target_mention} has been forgiven.\n"
            f"**Current Warns:** {remaining_warns} left."
            f"{unmute_text}"
        )
    else:
        await message.reply(
            f"✅ **Clean Slate!**\n"
            f"{target_mention} has **0** warnings."
            f"{unmute_text}"
        )


# High-speed RAM memory: cache[chat_id][user_id] = deque([(timestamp, msg_id), ...])
flood_cache = defaultdict(lambda: defaultdict(lambda: deque(maxlen=7)))

FLOOD_LIMIT = 5
TIME_WINDOW = 10  # Seconds

@Client.on_message(filters.group & ~filters.bot, group=2)
async def flood_watcher(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    now = time.time()
    
    # 1. Quick enable check
    s = await get_warn_settings(chat_id)
    if not s["enabled"]:
        return

    # Add to RAM cache
    user_history = flood_cache[chat_id][user_id]
    user_history.append((now, message.id))
    
    # 2. Check for Flood (7 msgs in < 10s)
    if len(user_history) == FLOOD_LIMIT:
        time_diff = user_history[-1][0] - user_history[0][0]
        
        if time_diff <= TIME_WINDOW:
            msg_ids_to_delete = [item[1] for item in user_history]
            user_history.clear() # Reset cache
            
            try:
                # Delete the flood messages
                await client.delete_messages(chat_id, msg_ids_to_delete)
                
                # Issue Warning in Database
                current_warns = await add_user_warn(chat_id, user_id)
                max_warns = s["max_warns"]
                
                # Check if punishment is needed
                if current_warns >= max_warns and s["punishment"] != "off":
                    punishment = s["punishment"]
                    action_txt = ""
                    
                    if punishment == "mute":
                        await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
                        action_txt = "🔇 **Muted**"
                        await increment_stat(chat_id, deleted=FLOOD_LIMIT, muted=1)
                        
                    elif punishment == "kick":
                        await client.ban_chat_member(chat_id, user_id)
                        await client.unban_chat_member(chat_id, user_id) # Kicks them
                        action_txt = "❗️ **Kicked**"
                        await increment_stat(chat_id, deleted=FLOOD_LIMIT)
                        
                    elif punishment == "ban":
                        await client.ban_chat_member(chat_id, user_id)
                        action_txt = "🚫 **Banned**"
                        await increment_stat(chat_id, deleted=FLOOD_LIMIT, banned=1)
                        
                    # Reset their warns since they were punished
                    await reset_user_warns(chat_id, user_id)
                    
                    await message.reply(
                        f"⚠️ **Action Taken** ⚠️\n"
                        f"{message.from_user.mention} reached {current_warns}/{max_warns} warnings.\n"
                        f"**Punishment applied:** {action_txt}"
                    )
                    
                else:
                    # Just issue a warning
                    await increment_stat(chat_id, warns=1, deleted=FLOOD_LIMIT)
                    await message.reply(
                        f"⚠️ **FLOOD WARNING** ⚠️\n"
                        f"{message.from_user.mention}, please stop spamming!\n"
                        f"**Warns:** {current_warns}/{max_warns}"
                    )
                    
            except Exception as e:
                print(f"Failed to execute mod action in {chat_id}: {e}")


async def weekly_audit_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            
            # Run exactly on Sunday (6) at 20:00 UTC
            if now.weekday() == 6 and now.hour == 20 and now.minute == 0:
                groups = await get_all_enabled_groups()
                
                for group in groups:
                    chat_id = group["chat_id"]
                    
                    # Fetch stats and instantly wipe them from DB
                    stats = await pop_weekly_stats(chat_id)
                    
                    if any(val > 0 for val in stats.values()):
                        report = (
                            "📊 **Weekly Auto-Mod Report**\n\n"
                            f"🔹 **Auto-Warns Issued:** {stats['warns_issued']}\n"
                            f"🔹 **Messages Deleted:** {stats['msgs_deleted']}\n"
                            f"🔹 **Users Muted:** {stats['users_muted']}\n"
                            f"🔹 **Users Banned:** {stats['users_banned']}\n"
                            f"🔹 **Warnings Decayed:** {stats['warns_decayed']}\n\n"
                            "🛡 *Your group is 100% secure!*"
                        )
                        
                        try:
                            await app.send_message(chat_id, report)
                        except Exception as e:
                            print(f"Failed to send report to {chat_id}: {e}")
                
                # Sleep 60 seconds so it doesn't trigger twice in the same minute
                await asyncio.sleep(60) 
                
        except Exception as e:
            print(f"Audit Loop Error: {e}")
            
        await asyncio.sleep(20) # Normal check interval
