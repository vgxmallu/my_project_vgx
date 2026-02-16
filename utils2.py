from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_wizard_kb(data):
    """Generates the Creation Dashboard"""
    # Visual Toggles
    pin = "✅" if data.get('pin') else "❌"
    dl = "✅" if data.get('del_last') else "❌"
    
    # Interval formatting
    mins = data.get('interval', 0)
    int_txt = f"{mins}m" if mins > 0 else "One-Time"

    # Auto Delete formatting
    ad = data.get('auto_del', 0)
    ad_txt = f"{ad}s" if ad > 0 else "Off"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Content", callback_data="wiz_set_content"),
            InlineKeyboardButton("🎯 Target", callback_data="wiz_set_target")
        ],
        [
            InlineKeyboardButton(f"📌 Pin: {pin}", callback_data="wiz_toggle_pin"),
            InlineKeyboardButton(f"♻️ Del Last: {dl}", callback_data="wiz_toggle_dellast")
        ],
        [
            InlineKeyboardButton(f"⏲ Interval: {int_txt}", callback_data="wiz_set_interval"),
            InlineKeyboardButton(f"⏳ Auto-Del: {ad_txt}", callback_data="wiz_set_autodel")
        ],
        [
            InlineKeyboardButton("✅ SAVE & START", callback_data="wiz_save"),
            InlineKeyboardButton("❌ Cancel", callback_data="wiz_cancel")
        ]
    ])

def get_job_controls(job_id, paused):
    """Generates controls for an active job"""
    pause_btn = "▶️ Resume" if paused else "⏸ Pause"
    pause_data = f"mngr_resume_{job_id}" if paused else f"mngr_pause_{job_id}"
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(pause_btn, callback_data=pause_data),
            InlineKeyboardButton("✏️ Edit Msg", callback_data=f"mngr_edit_{job_id}")
        ],
        [
            InlineKeyboardButton("⏱ Intervals", callback_data=f"mngr_interval_{job_id}"),
            InlineKeyboardButton("🗑 DELETE", callback_data=f"mngr_delete_{job_id}")
        ],
        [InlineKeyboardButton("🔙 Back to List", callback_data="myjobs_refresh")]
    ])
