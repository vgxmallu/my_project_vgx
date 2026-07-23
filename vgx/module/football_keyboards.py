from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔴 Live Scores", callback_data="af_live"),
            InlineKeyboardButton("⚙️ Target Controls", callback_data="af_settings_menu")
        ],
        [
            InlineKeyboardButton("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", callback_data="af_league_39"),
            InlineKeyboardButton("🇪🇸 La Liga", callback_data="af_league_140")
        ],
        [
            InlineKeyboardButton("🇮🇹 Serie A", callback_data="af_league_135"),
            InlineKeyboardButton("🇩🇪 Bundesliga", callback_data="af_league_78")
        ],
        [
            InlineKeyboardButton("🇪🇺 Champions League", callback_data="af_league_2")
        ]
    ])

def league_menu_keyboard(league_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Standings", callback_data=f"af_standings_{league_id}"),
            InlineKeyboardButton("🎯 Top Scorers", callback_data=f"af_topscorers_{league_id}")
        ],
        [InlineKeyboardButton("⬅️ Main Menu", callback_data="af_main")]
    ])

def settings_menu_keyboard(settings: dict, active_target: int = None):
    auto_del = settings.get("auto_delete", 0)
    auto_del_str = f"{auto_del}s" if auto_del > 0 else "OFF"
    
    pin_str = "ENABLED ✅" if settings.get("pin_messages", False) else "DISABLED ❌"
    
    sched = settings.get("live_schedule", 0)
    sched_map = {0: "OFF", 60: "1m", 300: "5m", 1200: "20m", 1800: "30m", 3600: "1h"}
    sched_str = sched_map.get(sched, "OFF")
    
    target_str = f"`{active_target}`" if active_target else "Current Chat"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🎯 Target Group: {target_str}", callback_data="af_set_target")],
        [
            InlineKeyboardButton(f"⏱ Auto-Delete: {auto_del_str}", callback_data="af_cycle_autodel"),
            InlineKeyboardButton(f"📌 Auto-Pin: {pin_str}", callback_data="af_toggle_pin")
        ],
        [
            InlineKeyboardButton(f"📡 Scheduled Live: {sched_str}", callback_data="af_cycle_sched")
        ],
        [InlineKeyboardButton("🧩 Module Toggles", callback_data="af_module_settings")],
        [InlineKeyboardButton("⬅️ Main Menu", callback_data="af_main")]
    ])

def module_toggle_keyboard(modules: dict):
    def state(key): return "✅" if modules.get(key, True) else "❌"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Live Scores: {state('live')}", callback_data="af_modtoggle_live"),
            InlineKeyboardButton(f"Standings: {state('standings')}", callback_data="af_modtoggle_standings")
        ],
        [
            InlineKeyboardButton(f"Top Scorers: {state('topscorers')}", callback_data="af_modtoggle_topscorers"),
            InlineKeyboardButton(f"Predictions: {state('predict')}", callback_data="af_modtoggle_predict")
        ],
        [
            InlineKeyboardButton(f"Lineups: {state('lineup')}", callback_data="af_modtoggle_lineup"),
            InlineKeyboardButton(f"Injuries: {state('injuries')}", callback_data="af_modtoggle_injuries")
        ],
        [InlineKeyboardButton(f"Head to Head: {state('h2h')}", callback_data="af_modtoggle_h2h")],
        [InlineKeyboardButton("⬅️ Back to Controls", callback_data="af_settings_menu")]
    ])

def back_to_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Main Menu", callback_data="af_main")]])
