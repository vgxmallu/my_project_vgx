from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.automod_db import get_warn_settings, update_warn_settings

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
