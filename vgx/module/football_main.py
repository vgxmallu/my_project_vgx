from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram import Client, filters
 
from vgx.module.football_api import get_live_scores, get_standings
from vgx.module.football_schedule import send_managed_message
from vgx.database.footballdb import get_group_settings, update_group_setting, toggle_group_module, clear_user_target, set_user_target, get_user_target




def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔴 Live Scores", callback_data="fb_live"), 
            InlineKeyboardButton("⚙️ Group Settings", callback_data="cfg_menu")
        ],
        [
            InlineKeyboardButton("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", callback_data="fb_standings_39"), 
            InlineKeyboardButton("🇪🇸 La Liga", callback_data="fb_standings_140")
        ],
        [
            InlineKeyboardButton("🇮🇹 Serie A", callback_data="fb_standings_135"), 
            InlineKeyboardButton("🇩🇪 Bundesliga", callback_data="fb_standings_78")
        ],
        [
            InlineKeyboardButton("🇫🇷 Ligue 1", callback_data="fb_standings_61"), 
            InlineKeyboardButton("🇪🇺 Champions League", callback_data="fb_standings_2")
        ]
    ])

def settings_menu(settings: dict, active_target: int = None):
    auto_del = f"{settings.get('auto_delete', 0)}s" if settings.get("auto_delete", 0) > 0 else "OFF"
    pin_str = "ON ✅" if settings.get("pin_messages", False) else "OFF ❌"
    sched_str = {0: "OFF", 60: "1m", 300: "5m", 1200: "20m", 1800: "30m", 3600: "1h"}.get(settings.get("live_schedule", 0), "OFF")
    
    # Target row logic: Add a clear button if a target is currently active
    target_row = [InlineKeyboardButton(f"🎯 Target: {active_target or 'Current Chat'}", callback_data="cfg_target_info")]
    if active_target:
        target_row.append(InlineKeyboardButton("❌ Clear Target", callback_data="cfg_clear_target"))

    return InlineKeyboardMarkup([
        target_row,
        [InlineKeyboardButton(f"⏱ Auto-Delete: {auto_del}", callback_data="cfg_cycle_autodel"), InlineKeyboardButton(f"📌 Pin: {pin_str}", callback_data="cfg_toggle_pin")],
        [InlineKeyboardButton(f"📡 Scheduled Live: {sched_str}", callback_data="cfg_cycle_sched")],
        [InlineKeyboardButton("🧩 Toggle Modules", callback_data="cfg_modules")],
        [InlineKeyboardButton("⬅️ Back", callback_data="fb_main")]
    ])

def module_menu(modules: dict):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Live: {'✅' if modules.get('live', True) else '❌'}", callback_data="cfg_mod_live")],
        [InlineKeyboardButton(f"Standings: {'✅' if modules.get('standings', True) else '❌'}", callback_data="cfg_mod_standings")],
        [InlineKeyboardButton("⬅️ Back to Settings", callback_data="cfg_menu")]
    ])

def back_btn(): 
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="fb_main")]])

#====================================================

@Client.on_message(filters.command("football_f"))
async def stajjt_command(client: Client, message: Message):
    await send_managed_message(
        client, message.chat.id,
        "⚽ **Ultimate API-Football Bot**\nWelcome! Select an option:",
        reply_markup=main_menu()
    )

# Strict Regex Callback for Football Features
@Client.on_callback_query(filters.regex(r"^fb_(main|live|standings)(?:_(\d+))?$"))
async def football_callbacks(client: Client, query: CallbackQuery):
    await query.answer()
    
    action = query.matches[0].group(1)
    param = query.matches[0].group(2)
    
    settings = await get_group_settings(query.message.chat.id)
    modules = settings.get("modules", {})
    
    if action in modules and not modules[action]:
        await query.message.edit_text("🚫 **This feature is disabled by administrators.**", reply_markup=back_btn())
        return

    try:
        if action == "main":
            await query.message.edit_text("⚽ **Ultimate API-Football Bot**", reply_markup=main_menu())
        elif action == "live":
            await query.message.edit_text("⏳ Fetching...", reply_markup=None)
            await query.message.edit_text(await get_live_scores(), reply_markup=back_btn())
        elif action == "standings":
            await query.message.edit_text("⏳ Fetching...", reply_markup=None)
            await query.message.edit_text(await get_standings(int(param)), reply_markup=back_btn())
    except Exception as e:
        await query.message.edit_text(f"⚠️ Error: `{str(e)}`", reply_markup=back_btn())

#====================================================


@Client.on_message(filters.command("f_settarget"))
async def set_tsgmand(client: Client, message: Message):
    try:
        target_id = int(message.command[1])
        await set_user_target(message.from_user.id, target_id)
        await message.reply_text(f"✅ **Target Group set to:** `{target_id}`\nSettings changed via PM will now apply to this group!")
    except (IndexError, ValueError):
        await message.reply_text("⚠️ **Usage:** `/settarget <group_id>`")

# Strict Regex Callback for Configuration
@Client.on_callback_query(filters.regex(r"^cfg_(menu|target_info|clear_target|cycle_autodel|toggle_pin|cycle_sched|modules|mod_.*)$"))
async def settings_callbacks(client: Client, query: CallbackQuery):
    await query.answer()
    user_id = query.from_user.id
    
    # Target resolution: If in PM, check if user has a target group. Otherwise use current chat.
    active_target = await get_user_target(user_id) if query.message.chat.type.name == "PRIVATE" else None
    chat_id = active_target if active_target else query.message.chat.id
    
    action = query.matches[0].group(1)

    if action == "menu":
        settings = await get_group_settings(chat_id)
        await query.message.edit_text(f"⚙️ **Group Controls**\nConfiguring ID: `{chat_id}`", reply_markup=settings_menu(settings, active_target))

    elif action == "target_info":
        await query.message.edit_text("🎯 **Target Group Setup:**\n1. Add bot to group.\n2. In this PM send `/settarget <group_id>`.\n\n*Use the 'Clear Target' button to revert back to controlling this current chat.*", reply_markup=back_btn())

    elif action == "clear_target":
        await clear_user_target(user_id)
        # Revert chat_id back to the current chat (PM)
        new_chat_id = query.message.chat.id
        settings = await get_group_settings(new_chat_id)
        await query.message.edit_text(
            "✅ **Target Cleared!**\nYou are now managing settings for this current chat again.", 
            reply_markup=settings_menu(settings, None)
        )

    elif action == "cycle_autodel":
        current = (await get_group_settings(chat_id)).get("auto_delete", 0)
        cycle = [0, 30, 300, 400, 2400]
        next_val = cycle[(cycle.index(current) + 1) % len(cycle)] if current in cycle else 0
        await update_group_setting(chat_id, "auto_delete", next_val)
        await query.message.edit_reply_markup(reply_markup=settings_menu(await get_group_settings(chat_id), active_target))

    elif action == "toggle_pin":
        new_pin = not (await get_group_settings(chat_id)).get("pin_messages", False)
        await update_group_setting(chat_id, "pin_messages", new_pin)
        await query.message.edit_reply_markup(reply_markup=settings_menu(await get_group_settings(chat_id), active_target))

    elif action == "cycle_sched":
        current = (await get_group_settings(chat_id)).get("live_schedule", 0)
        cycle = [0, 60, 300, 1200, 1800, 3600] # 1m, 5m, 20m, 30m, 1h
        next_val = cycle[(cycle.index(current) + 1) % len(cycle)] if current in cycle else 0
        await update_group_setting(chat_id, "live_schedule", next_val)
        await query.message.edit_reply_markup(reply_markup=settings_menu(await get_group_settings(chat_id), active_target))

    elif action == "modules":
        settings = await get_group_settings(chat_id)
        await query.message.edit_text(f"🧩 **Modules**\nID: `{chat_id}`", reply_markup=module_menu(settings.get("modules", {})))

    elif action.startswith("mod_"):
        module_name = action.replace("mod_", "")
        await toggle_group_module(chat_id, module_name)
        settings = await get_group_settings(chat_id)
        await query.message.edit_reply_markup(reply_markup=module_menu(settings.get("modules", {})))
