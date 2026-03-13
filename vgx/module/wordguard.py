from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from vgx.database.wordguard_db import get_guard_settings, update_guard_settings, add_user_warn, reset_user_warns, add_custom_word, remove_custom_word

import asyncio
from pyrogram.types import ChatPermissions






async def is_admin(client, chat_id, user_id):
    member = await client.get_chat_member(chat_id, user_id)
    return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

def build_warn_panel(s: dict):
    chat_id = s["chat_id"]
    p = s["punishment"]
    m = s["max_warns"]
    
    # Format buttons to highlight the active choice
    b_off = "✖️ Off ✅" if p == "Off" else "✖️ Off"
    b_kick = "❗ Kick ✅" if p == "Kick" else "❗ Kick"
    b_mute = "🔇 Mute ✅" if p == "Mute" else "🔇 Mute"
    b_ban = "🚫 Ban ✅" if p == "Ban" else "🚫 Ban"

    # Dynamic numbers row
    nums = []
    for i in range(2, 7):
        text = f"{i} ✅" if m == i else str(i)
        nums.append(InlineKeyboardButton(text, callback_data=f"ws_num_{chat_id}_{i}"))

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Warned List", callback_data=f"ws_list_{chat_id}")],
        [
            InlineKeyboardButton(b_off, callback_data=f"ws_pun_{chat_id}_Off"),
            InlineKeyboardButton(b_kick, callback_data=f"ws_pun_{chat_id}_Kick")
        ],
        [
            InlineKeyboardButton(b_mute, callback_data=f"ws_pun_{chat_id}_Mute"),
            InlineKeyboardButton(b_ban, callback_data=f"ws_pun_{chat_id}_Ban")
        ],
        [InlineKeyboardButton("🚫⏱ Set ban duration", callback_data=f"ws_dur_{chat_id}")],
        nums # The bottom row of numbers
    ])

@Client.on_message(filters.command("warnsettings") & filters.group)
async def cmd_warnsebbttings(client, message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
        
    chat_id = message.chat.id
    s = await get_guard_settings(chat_id)
    
    text = (
        "❗ **User warnings for Eord guard**\n"
        "The warning system allows you to give warnings to users for incorrect behavior "
        "in the group, before actually punishing them.\n\n"
        "From this menu you can set:\n"
        "• the punishment for users who exceed the maximum of warnings allowed\n"
        "• the maximum number of warns allowed\n\n"
        f"**Punishment:** {s['punishment']}\n"
        f"**Max Warns allowed:** {s['max_warns']}"
    )
    
    await message.reply(text, reply_markup=build_warn_panel(s))

@Client.on_callback_query(filters.regex(r"^ws_(?P<action>pun|num|list|dur)_(?P<chat_id>-?\d+)_?(?P<val>\w+)?$"))
async def warn_ui_router(client, query):
    action = query.matches[0].group("action")
    chat_id = int(query.matches[0].group("chat_id"))
    val = query.matches[0].group("val")
    
    if action == "pun":
        await update_guard_settings(chat_id, punishment=val)
    elif action == "num":
        await update_guard_settings(chat_id, max_warns=int(val))
    elif action == "dur":
        return await query.answer("Type /setduration <hours> to set temporary ban limits!", show_alert=True)
    elif action == "list":
        return await query.answer("Fetching warned users from database...", show_alert=True)

    # Refresh UI
    s = await get_guard_settings(chat_id)
    text = (
        "❗ **User warnings for Eord guard**\n"
        "The warning system allows you to give warnings to users for incorrect behavior "
        "in the group, before actually punishing them.\n\n"
        "From this menu you can set:\n"
        "• the punishment for users who exceed the maximum of warnings allowed\n"
        "• the maximum number of warns allowed\n\n"
        f"**Punishment:** {s['punishment']}\n"
        f"**Max Warns allowed:** {s['max_warns']}"
    )
    await query.message.edit_text(text, reply_markup=build_warn_panel(s))

#===============


@Client.on_message(filters.command("wordguard") & filters.group)
async def cmd_wordguard(client, message):
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    if len(message.command) < 2 or message.command[1].lower() not in ["on", "off"]:
        return await message.reply("❌ **Usage:** `/wordguard on` or `/wordguard off`")

    turn_on = message.command[1].lower() == "on"
    await update_guard_settings(message.chat.id, enabled=turn_on)
    await message.reply(f"🛡 **Word Guard is now {'ENABLED' if turn_on else 'DISABLED'}!**")

@Client.on_message(filters.command("setword") & filters.group)
async def cmd_setword(client, message):
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/setword <bad_word>`")
        
    bad_word = " ".join(message.command[1:]).lower()
    await add_custom_word(message.chat.id, bad_word)
    await message.reply(f"✅ `{bad_word}` added to the blocklist!")

@Client.on_message(filters.command("delword") & filters.group)
async def cmd_delword(client, message):
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/delword <bad_word>`")
        
    bad_word = " ".join(message.command[1:]).lower()
    await remove_custom_word(message.chat.id, bad_word)
    await message.reply(f"🗑 `{bad_word}` removed from the blocklist!")

@Client.on_message(filters.command("badlist") & filters.group)
async def cmd_badlist(client, message):
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    
    s = await get_guard_settings(message.chat.id)
    words = s.get("custom_words", [])
    
    if not words:
        return await message.reply("🛡 The custom blocklist is currently empty.")
        
    formatted_list = "\n".join([f"• `{w}`" for w in words])
    await message.reply(f"📜 **Active Blocklist:**\n\n{formatted_list}")

#=====================


GLOBAL_FILTERS = {
    "🔞 18+ Content": ["porn", "xxx", "onlyfans"],
    "🚫 Scams": ["free crypto", "ponzi"]
}

@Client.on_message(filters.group & filters.text & ~filters.bot, group=1)
async def auto_mod_engine(client, message):
    if not message.from_user: return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    s = await get_guard_settings(chat_id)
    
    if not s["enabled"] or await is_admin(client, chat_id, user_id): 
        return

    text_lower = message.text.lower()
    triggered_category = None
    
    # Check Global Words
    for cat, words in GLOBAL_FILTERS.items():
        if any(w in text_lower for w in words):
            triggered_category = cat
            break

    # Check Custom Words
    if not triggered_category:
        if any(w in text_lower for w in s.get("custom_words", [])):
            triggered_category = "🚫 Custom Blocked Word"

    if triggered_category:
        try:
            await message.delete()
            
            # Add 1 Warning to the User
            current_warns = await add_user_warn(chat_id, user_id)
            max_warns = s["max_warns"]
            
            # --- PUNISHMENT CHECK ---
            if current_warns >= max_warns and s["punishment"] != "Off":
                punish = s["punishment"]
                
                if punish == "Ban":
                    await client.ban_chat_member(chat_id, user_id)
                    action_text = "banned permanently"
                elif punish == "Kick":
                    await client.ban_chat_member(chat_id, user_id)
                    await client.unban_chat_member(chat_id, user_id) # Unbanning immediately acts as a Kick
                    action_text = "kicked from the group"
                elif punish == "Mute":
                    await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
                    action_text = "muted permanently"
                    
                # Reset warns after punishment
                await reset_user_warns(chat_id, user_id)
                
                await message.reply(
                    f"⚖️ **JUSTICE SERVED** ⚖️\n"
                    f"👤 {message.from_user.mention} reached `{max_warns}/{max_warns}` warnings.\n"
                    f"🔨 **Action:** They have been {action_text}."
                )
            else:
                # --- STANDARD WARNING ---
                warning_msg = await message.reply(
                    f"🛑 **Message Deleted!**\n"
                    f"👤 **User:** {message.from_user.mention}\n"
                    f"📋 **Reason:** {triggered_category}\n"
                    f"⚠️ **Warning:** `{current_warns}/{max_warns}`\n\n"
                    f"*(Reach {max_warns} warnings and you will face a {s['punishment']}.)*"
                )
                await asyncio.sleep(10)
                await warning_msg.delete()
                
        except Exception as e:
            print(f"Auto-Mod Error: {e}")
