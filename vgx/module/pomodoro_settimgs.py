from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.pomodoro_db import get_pomo_settings, update_pomo_settings

def build_pomo_menu(chat_id: int, is_enabled: bool):
    btn_text = "🟢 Pomodoro: ENABLED" if is_enabled else "🔴 Pomodoro: DISABLED"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_text, callback_data=f"pomo_tgl_{chat_id}")]
    ])

@Client.on_message(filters.command("pomotarget") & filters.private)
async def pomo_target_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/pomotarget -100123456789`")
        
    try:
        chat_id = int(message.command[1])
        s = await get_pomo_settings(chat_id)
        
        await message.reply(
            f"🍅 **Pomodoro Sprint Manager**\n🎯 **Target:** `{chat_id}`", 
            reply_markup=build_pomo_menu(chat_id, s["enabled"])
        )
    except ValueError:
        await message.reply("❌ Please provide a valid numeric Group ID.")

@Client.on_callback_query(filters.regex(r"^pomo_tgl_(?P<chat_id>-?\d+)$"))
async def pomo_toggle_callback(client, query):
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_pomo_settings(chat_id)
    
    # Toggle the state
    new_state = not s["enabled"]
    await update_pomo_settings(chat_id, new_state)
    
    # Refresh UI
    await query.message.edit_reply_markup(
        reply_markup=build_pomo_menu(chat_id, new_state)
    )
    await query.answer(f"Module {'Enabled' if new_state else 'Disabled'}!")
