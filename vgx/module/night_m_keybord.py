from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_settings_kb(data):
    # Visual Toggles
    en = "✅" if data['enabled'] else "❌"
    warn = "✅" if data.get('warning') else "❌"
    clean = "✅" if data.get('auto_clean') else "❌"
    
    # Permission Toggles (What is ALLOWED at night?)
    p = data['perms']
    txt = "🟢" if p['text'] else "🔴"
    med = "🟢" if p['media'] else "🔴"
    stk = "🟢" if p['stickers'] else "🔴"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Night Mode: {en}", callback_data="nm_toggle_main")],
        [
            InlineKeyboardButton(f"🕒 Start: {data['night_start']}", callback_data="nm_set_start"),
            InlineKeyboardButton(f"☀️ End: {data['night_end']}", callback_data="nm_set_end")
        ],
        [InlineKeyboardButton(f"🌍 Timezone: {data['timezone']}", callback_data="nm_set_tz")],
        [InlineKeyboardButton("--- 🛡 RESTRICTIONS ---", callback_data="ignore")],
        [
            InlineKeyboardButton(f"Text {txt}", callback_data="nm_perm_text"),
            InlineKeyboardButton(f"Media {med}", callback_data="nm_perm_media"),
            InlineKeyboardButton(f"Stickers {stk}", callback_data="nm_perm_stickers")
        ],
        [InlineKeyboardButton("--- ⚙️ EXTRAS ---", callback_data="ignore")],
        [
            InlineKeyboardButton(f"⚠️ Warning: {warn}", callback_data="nm_toggle_warn"),
            InlineKeyboardButton(f"🧹 Auto-Clean: {clean}", callback_data="nm_toggle_clean")
        ],
        [
            InlineKeyboardButton("🚨 Emergency Unlock", callback_data="nm_emergency"),
            InlineKeyboardButton("👑 Manage VIPs", callback_data="nm_vips")
        ],
        [InlineKeyboardButton("❌ Close Menu", callback_data="nm_close")]
    ])
