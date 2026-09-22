import asyncio
from datetime import datetime
from pyrogram.types import ChatPermissions
from vgx.database.pomodoro_db import get_expired_sprints, remove_sprint, get_pomo_settings, update_pomo_settings


from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton 

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

async def pomodoro_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            expired_sprints = await get_expired_sprints(now)
            
            for sprint in expired_sprints:
                chat_id = sprint["chat_id"]
                
                try:
                    # Restore standard chat permissions
                    await app.set_chat_permissions(
                        chat_id,
                        ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_other_messages=True,
                            can_add_web_page_previews=True
                        )
                    )
                    
                    # Announce the break
                    await app.send_message(
                        chat_id, 
                        "🔔 **Sprint over!**\nThe chat is now unlocked. You have a well-deserved break! ☕️"
                    )
                except Exception as e:
                    print(f"Failed to unlock chat {chat_id}: {e}")
                
                # Remove from database so it doesn't trigger again
                await remove_sprint(chat_id)
                
        except Exception as e:
            print(f"Pomodoro Scheduler Error: {e}")
            
        await asyncio.sleep(10) # Check every 10 seconds
