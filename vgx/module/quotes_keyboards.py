from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu(chat_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Enable", callback_data=f"enable|{chat_id}"),
            InlineKeyboardButton("❌ Disable", callback_data=f"disable|{chat_id}")
        ],
        [
            InlineKeyboardButton("⏰ Interval", callback_data=f"intervals|{chat_id}"),
            InlineKeyboardButton("🗑 Auto-delete", callback_data=f"autodels|{chat_id}")
        ],
        [
            InlineKeyboardButton("♻ Delete-last", callback_data=f"dellast|{chat_id}"),
            InlineKeyboardButton("📌 Pin", callback_data=f"pin|{chat_id}")
        ],
        [
            InlineKeyboardButton("🎯 Set target", callback_data=f"target_info|{chat_id}"),
            InlineKeyboardButton("🧾 Show settings", callback_data=f"show|{chat_id}")
        ]
    ])

def interval_menu(chat_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1m", callback_data=f"setint|{chat_id}|60"),
            InlineKeyboardButton("5m", callback_data=f"setint|{chat_id}|300")
        ],
        [
            InlineKeyboardButton("20m", callback_data=f"setint|{chat_id}|1200"),
            InlineKeyboardButton("30m", callback_data=f"setint|{chat_id}|1800")
        ],
        [
            InlineKeyboardButton("1h", callback_data=f"setint|{chat_id}|3600")
        ],
        [
            InlineKeyboardButton("⬅ Back", callback_data=f"back|{chat_id}")
        ]
    ])

def autodel_menu(chat_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("30s", callback_data=f"setdel|{chat_id}|30"),
            InlineKeyboardButton("300s", callback_data=f"setdel|{chat_id}|300")
        ],
        [
            InlineKeyboardButton("400s", callback_data=f"setdel|{chat_id}|400"),
            InlineKeyboardButton("2400s", callback_data=f"setdel|{chat_id}|2400")
        ],
        [
            InlineKeyboardButton("Disable", callback_data=f"setdel|{chat_id}|0"),
            InlineKeyboardButton("⬅ Back", callback_data=f"back|{chat_id}")
        ]
    ])
