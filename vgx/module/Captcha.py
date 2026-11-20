import asyncio
import os
import random
import time
from pymongo import AsyncMongoClient, IndexModel
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import (
    CallbackQuery,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from vgx import app

try:
    from config import Config
except ImportError:
    Config = None

MONGO_URI = (
    getattr(Config, "MONGO_URL", None)
    or os.getenv("MONGO_URL")
)
MONGO_DB_NAME = "captcha_botvgx"

ALLOWED_TIME_MINUTES = [5, 10, 20, 30, 40, 50, 60]
ALLOWED_PENALTIES = ["mute", "kick", "ban"]
ALLOWED_MODES = ["button", "math", "emoji", "word"]
ALLOWED_ATTEMPTS = [3, 5]
WARN_LIMIT = 3

EMOJI_POOL = [
    # Animals (28)
    "🦊", "🐼", "🦁", "🐸", "🐙", "🦉", "🐺",
    "🐢", "🐬", "🦋", "🐝", "🦔", "🦖", "🦩",
    "🦈", "🐨", "🐪", "🦚", "🐧", "🦄", "🦀",
    "🦘", "🦥", "🦦", "🐊", "🦢", "🐞", "🐳",
    "🍎", "🍕", "🍔", "🌮", "🍣", "🍩", "🍓",
    "🥑", "🍉", "🥐", "🍿", "🧁", "🍍", "🥨",
    "🍒", "🥞", "🥥", "🍋", "🥟", "🧇", "🍇",
    "🔥", "⚡", "🌙", "🍀", "🌊", "🌈", "❄️",
    "🌋", "🌵", "🌻", "🍄", "🪐", "☀️", "🌪️",
    "🍁", "🌴", "⛄", "🌟", "🌸", "🪵", "🪨",
    "🚀", "💎", "🎮", "🎧", "🧩", "🛡️", "🔑",
    "🧭", "🎯", "🎸", "🏮", "⏳", "🔭", "🪄",
    "🪁", "🚲", "⚓", "💻", "📷", "🔦", "🪫",
    "⚽", "🏀", "🏆", "🎲", "👑", "🔔", "🎈",
    "🎁", "💣", "🧪", "🧭", "🏝️", "🗽", "🎡",
    "🚂", "🚁", "🛸", "🧸", "🪩", "🪄", "🕯️",
]


WORD_POOL = [
    "ember", "orbit", "cobalt", "harbor", "zenith", "velvet",
    "prism", "atlas", "cipher", "meadow", "quartz", "summit",
    "anchor", "falcon", "echo", "ripple", "timber", "breeze",
]

DEFAULT_GROUP_CONFIG = {
    "enabled": True,
    "time_minutes": 5,
    "penalty": "mute",
    "mode": "button",
    "max_attempts": 3,
    "delete_service_msg": False,
    "clean_service": False,
    "lockdown": False,
}

_mongo_client: AsyncMongoClient | None = None
_indexes_ready = False
_active_timers: dict[tuple[int, int], asyncio.Task] = {}

RESTRICTED_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_media_messages=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)

LOCKDOWN_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_media_messages=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)

UNRESTRICTED_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)


def safe_truncate(text: str, max_length: int = 3800) -> str:
    """Safely truncates text to stay within Telegram's message length limit."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n... _(Output truncated)_"


async def is_chat_admin(client: Client, chat_id: int, user_id: int | None) -> bool:
    """Checks whether a user is a chat owner or administrator."""
    if not user_id:
        return False
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}
    except Exception:
        return False


async def get_db():
    """Returns the AsyncDatabase instance and ensures indexes exist."""
    global _mongo_client, _indexes_ready
    if _mongo_client is None:
        _mongo_client = AsyncMongoClient(MONGO_URI)

    db = _mongo_client[MONGO_DB_NAME]
    if not _indexes_ready:
        await db["pending_captchas"].create_indexes([
            IndexModel([("chat_id", 1), ("user_id", 1)], unique=True),
            IndexModel([("expires_at", 1)]),
        ])
        await db["captcha_groups"].create_indexes([
            IndexModel([("chat_id", 1)], unique=True),
            IndexModel([("enabled", 1)]),
        ])
        await db["captcha_mod_logs"].create_indexes([
            IndexModel([("chat_id", 1), ("created_at", -1)]),
            IndexModel([("chat_id", 1), ("user_id", 1)]),
        ])
        _indexes_ready = True
    return db


async def get_captchas_collection():
    db = await get_db()
    return db["pending_captchas"]


async def get_groups_collection():
    db = await get_db()
    return db["captcha_groups"]


async def get_mod_logs_collection():
    db = await get_db()
    return db["captcha_mod_logs"]


def _normalize_group_doc(
    chat_id: int, doc: dict | None, title: str | None = None, updated_by: int | None = None
) -> dict:
    base = dict(DEFAULT_GROUP_CONFIG)
    if doc:
        for k in DEFAULT_GROUP_CONFIG:
            if k in doc and doc[k] is not None:
                base[k] = doc[k]

    if base["time_minutes"] not in ALLOWED_TIME_MINUTES:
        base["time_minutes"] = DEFAULT_GROUP_CONFIG["time_minutes"]
    if base["penalty"] not in ALLOWED_PENALTIES:
        base["penalty"] = DEFAULT_GROUP_CONFIG["penalty"]
    if base["mode"] not in ALLOWED_MODES:
        base["mode"] = DEFAULT_GROUP_CONFIG["mode"]
    if base["max_attempts"] not in ALLOWED_ATTEMPTS:
        base["max_attempts"] = DEFAULT_GROUP_CONFIG["max_attempts"]

    resolved_title = title or (doc.get("title") if doc else None) or str(chat_id)
    return {
        "chat_id": chat_id,
        "title": resolved_title,
        "enabled": bool(base["enabled"]),
        "time_minutes": int(base["time_minutes"]),
        "penalty": str(base["penalty"]),
        "mode": str(base["mode"]),
        "max_attempts": int(base["max_attempts"]),
        "delete_service_msg": bool(base["delete_service_msg"]),
        "clean_service": bool(base["clean_service"]),
        "lockdown": bool(base["lockdown"]),
        "updated_by": (
            updated_by if updated_by is not None else (doc.get("updated_by") if doc else None)
        ),
        "updated_at": time.time(),
    }


async def upsert_group_config(
    chat_id: int,
    title: str | None = None,
    enabled: bool | None = None,
    time_minutes: int | None = None,
    penalty: str | None = None,
    mode: str | None = None,
    max_attempts: int | None = None,
    delete_service_msg: bool | None = None,
    clean_service: bool | None = None,
    lockdown: bool | None = None,
    updated_by: int | None = None,
) -> dict:
    """Creates or updates a group's captcha & moderation configuration in MongoDB."""
    col = await get_groups_collection()
    existing = await col.find_one({"chat_id": chat_id})
    merged = _normalize_group_doc(chat_id, existing, title=title, updated_by=updated_by)

    if enabled is not None:
        merged["enabled"] = bool(enabled)
    if time_minutes is not None and int(time_minutes) in ALLOWED_TIME_MINUTES:
        merged["time_minutes"] = int(time_minutes)
    if penalty is not None and penalty.lower() in ALLOWED_PENALTIES:
        merged["penalty"] = penalty.lower()
    if mode is not None and mode.lower() in ALLOWED_MODES:
        merged["mode"] = mode.lower()
    if max_attempts is not None and int(max_attempts) in ALLOWED_ATTEMPTS:
        merged["max_attempts"] = int(max_attempts)
    if delete_service_msg is not None:
        merged["delete_service_msg"] = bool(delete_service_msg)
    if clean_service is not None:
        merged["clean_service"] = bool(clean_service)
    if lockdown is not None:
        merged["lockdown"] = bool(lockdown)

    await col.update_one({"chat_id": chat_id}, {"$set": merged}, upsert=True)
    return merged


async def get_group_config(chat_id: int, title: str | None = None) -> dict:
    """Retrieves normalized group config, creating defaults in MongoDB if absent."""
    col = await get_groups_collection()
    doc = await col.find_one({"chat_id": chat_id})
    if doc is None:
        return await upsert_group_config(chat_id=chat_id, title=title)
    if title and doc.get("title") != title:
        await col.update_one(
            {"chat_id": chat_id}, {"$set": {"title": title, "updated_at": time.time()}}
        )
        doc["title"] = title
    return _normalize_group_doc(chat_id, doc, title=title)


async def get_all_managed_groups() -> list[dict]:
    col = await get_groups_collection()
    cursor = col.find({}).sort("title", 1)
    return [_normalize_group_doc(doc["chat_id"], doc) async for doc in cursor]


async def log_mod_action(
    chat_id: int,
    actor_id: int | None,
    action: str,
    target_user_id: int | None = None,
    reason: str = "",
) -> None:
    col = await get_mod_logs_collection()
    await col.insert_one({
        "chat_id": chat_id,
        "actor_id": actor_id,
        "target_user_id": target_user_id,
        "action": action,
        "reason": reason,
        "created_at": time.time(),
    })


async def get_recent_mod_logs(chat_id: int, limit: int = 8) -> list[dict]:
    col = await get_mod_logs_collection()
    cursor = col.find({"chat_id": chat_id}).sort("created_at", -1).limit(limit)
    return [doc async for doc in cursor]


async def get_user_warnings(chat_id: int, user_id: int) -> list[dict]:
    col = await get_mod_logs_collection()
    cursor = col.find({"chat_id": chat_id, "target_user_id": user_id, "action": "warn"}).sort(
        "created_at", -1
    )
    return [doc async for doc in cursor]


async def clear_user_warnings(chat_id: int, user_id: int) -> int:
    col = await get_mod_logs_collection()
    res = await col.delete_many({"chat_id": chat_id, "target_user_id": user_id, "action": "warn"})
    return res.deleted_count


async def upsert_pending_captcha(
    chat_id: int,
    user_id: int,
    msg_id: int,
    mode: str,
    expected_value: str,
    choices: list[str],
    expires_at: float,
    max_attempts: int = 3,
    attempts_used: int = 0,
    service_msg_id: int | None = None,
    penalty: str = "mute",
    delete_service_msg: bool = False,
) -> None:
    col = await get_captchas_collection()
    await col.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$set": {
                "chat_id": chat_id,
                "user_id": user_id,
                "msg_id": msg_id,
                "service_msg_id": service_msg_id,
                "mode": mode,
                "expected_value": str(expected_value),
                "choices": [str(c) for c in choices],
                "max_attempts": int(max_attempts),
                "attempts_used": int(attempts_used),
                "penalty": penalty,
                "delete_service_msg": bool(delete_service_msg),
                "expires_at": expires_at,
            }
        },
        upsert=True,
    )


async def increment_captcha_attempts(chat_id: int, user_id: int) -> dict | None:
    """Increments attempts_used by 1 in MongoDB and returns the updated document."""
    col = await get_captchas_collection()
    return await col.find_one_and_update(
        {"chat_id": chat_id, "user_id": user_id},
        {"$inc": {"attempts_used": 1}},
        return_document=True,
    )


async def get_pending_captcha(chat_id: int, user_id: int) -> dict | None:
    col = await get_captchas_collection()
    return await col.find_one({"chat_id": chat_id, "user_id": user_id})


async def get_chat_pending_captchas(chat_id: int) -> list[dict]:
    col = await get_captchas_collection()
    cursor = col.find({"chat_id": chat_id}).sort("expires_at", 1)
    return [doc async for doc in cursor]


async def delete_pending_captcha(chat_id: int, user_id: int) -> None:
    col = await get_captchas_collection()
    await col.delete_one({"chat_id": chat_id, "user_id": user_id})


async def get_all_pending_captchas() -> list[dict]:
    col = await get_captchas_collection()
    cursor = col.find({})
    return [doc async for doc in cursor]


def _cancel_timer(chat_id: int, user_id: int) -> None:
    key = (chat_id, user_id)
    task = _active_timers.pop(key, None)
    if task and not task.done() and task is not asyncio.current_task():
        task.cancel()


async def _delete_message_safe(client: Client, chat_id: int, message_id: int | None) -> None:
    if not message_id:
        return
    try:
        await client.delete_messages(chat_id, message_id)
    except Exception:
        pass


async def approve_user_captcha(
    client: Client,
    chat_id: int,
    user_id: int,
    msg_id: int | None = None,
    service_msg_id: int | None = None,
) -> None:
    """Unrestricts a user, deletes their MongoDB record, and cancels their timeout task."""
    await delete_pending_captcha(chat_id, user_id)
    _cancel_timer(chat_id, user_id)

    try:
        await client.restrict_chat_member(chat_id, user_id, UNRESTRICTED_PERMISSIONS)
    except Exception:
        pass

    await _delete_message_safe(client, chat_id, msg_id)
    await _delete_message_safe(client, chat_id, service_msg_id)


async def enforce_permanent_mute_and_cleanup(
    client: Client,
    chat_id: int,
    user_id: int,
    msg_id: int | None = None,
    service_msg_id: int | None = None,
    delete_service_msg: bool = False,
) -> None:
    """Permanently mutes a user who exhausted all captcha attempts and cleans up state."""
    await delete_pending_captcha(chat_id, user_id)
    _cancel_timer(chat_id, user_id)

    try:
        await client.restrict_chat_member(chat_id, user_id, RESTRICTED_PERMISSIONS)
    except Exception:
        pass

    if delete_service_msg:
        await _delete_message_safe(client, chat_id, service_msg_id)


async def apply_punishment_and_cleanup(
    client: Client,
    chat_id: int,
    user_id: int,
    msg_id: int | None = None,
    service_msg_id: int | None = None,
    penalty: str = "mute",
    delete_service_msg: bool = False,
) -> None:
    """Applies configured failure punishment (mute, kick, or ban) and cleans up state."""
    await delete_pending_captcha(chat_id, user_id)
    _cancel_timer(chat_id, user_id)

    normalized_penalty = (penalty or "mute").lower()
    try:
        if normalized_penalty == "ban":
            await client.ban_chat_member(chat_id, user_id)
        elif normalized_penalty == "kick":
            await client.ban_chat_member(chat_id, user_id)
            await client.unban_chat_member(chat_id, user_id)
        else:
            await client.restrict_chat_member(chat_id, user_id, RESTRICTED_PERMISSIONS)
    except Exception:
        pass

    await _delete_message_safe(client, chat_id, msg_id)
    if delete_service_msg:
        await _delete_message_safe(client, chat_id, service_msg_id)


async def _wait_until_expiry(
    client: Client, chat_id: int, user_id: int, msg_id: int, expires_at: float
) -> None:
    remaining = expires_at - time.time()
    if remaining > 0:
        await asyncio.sleep(remaining)

    record = await get_pending_captcha(chat_id, user_id)
    if record and record.get("msg_id") == msg_id:
        grp_cfg = await get_group_config(chat_id)
        penalty = record.get("penalty") or grp_cfg["penalty"]
        del_svc = bool(record.get("delete_service_msg", grp_cfg["delete_service_msg"]))
        await apply_punishment_and_cleanup(
            client,
            chat_id,
            user_id,
            msg_id=msg_id,
            service_msg_id=record.get("service_msg_id"),
            penalty=penalty,
            delete_service_msg=del_svc,
        )


def schedule_captcha_timer(
    client: Client, chat_id: int, user_id: int, msg_id: int, expires_at: float
) -> None:
    _cancel_timer(chat_id, user_id)
    _active_timers[(chat_id, user_id)] = asyncio.create_task(
        _wait_until_expiry(client, chat_id, user_id, msg_id, expires_at)
    )


async def recover_pending_captchas(client: Client) -> None:
    """Restores active captcha timers from MongoDB after a bot restart."""
    try:
        await get_db()
        records = await get_all_pending_captchas()
    except Exception:
        return

    now = time.time()
    for rec in records:
        chat_id = rec["chat_id"]
        user_id = rec["user_id"]
        msg_id = rec["msg_id"]
        expires_at = rec["expires_at"]

        if expires_at <= now:
            grp_cfg = await get_group_config(chat_id)
            penalty = rec.get("penalty") or grp_cfg["penalty"]
            del_svc = bool(rec.get("delete_service_msg", grp_cfg["delete_service_msg"]))
            await apply_punishment_and_cleanup(
                client,
                chat_id,
                user_id,
                msg_id=msg_id,
                service_msg_id=rec.get("service_msg_id"),
                penalty=penalty,
                delete_service_msg=del_svc,
            )
        else:
            schedule_captcha_timer(client, chat_id, user_id, msg_id, expires_at)


async def resolve_target_group(client: Client, raw_target: str) -> tuple[int, str] | tuple[None, str]:
    """Resolves a group chat ID (-100...) or @username into (chat_id, title)."""
    token = raw_target.strip()
    try:
        target_id: int | str = int(token) if token.lstrip("-").isdigit() else token
        chat = await client.get_chat(target_id)
        return chat.id, (chat.title or str(chat.id))
    except Exception as exc:
        return None, str(exc)


async def extract_target_user(
    client: Client, message: Message, extra_args: list[str]
) -> tuple[int | None, str, str]:
    """Extracts target user ID from a replied message or argument, returning (uid, label, reason)."""
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        reason = " ".join(extra_args).strip()
        return u.id, (u.first_name or str(u.id)), reason

    if not extra_args:
        return None, "", ""

    token = extra_args[0].strip()
    reason = " ".join(extra_args[1:]).strip()
    try:
        target: int | str = int(token) if token.isdigit() else token
        u = await client.get_users(target)
        return u.id, (u.first_name or str(u.id)), reason
    except Exception:
        return None, "", ""


def _build_captcha_challenge(
    mode: str, user_id: int, user_mention: str, cfg: dict
) -> tuple[str, str, list[str], InlineKeyboardMarkup]:
    """Builds prompt text, expected answer, choice list, and inline buttons for the active mode."""
    max_att = int(cfg.get("max_attempts", 3))
    meta_line = (
        f"🕒 **Time:** `{cfg['time_minutes']}m` | ⛔️ **Penalty:** `{cfg['penalty'].capitalize()}` | "
        f"🎯 **Attempts:** `{max_att}` (forever mute if exceeded)"
    )

    if mode == "math":
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        expected = str(num1 + num2)
        decoys = {str(num1 + num2 + d) for d in (-3, -2, -1, 1, 2, 3) if (num1 + num2 + d) > 0}
        choices = random.sample(sorted(decoys), k=min(3, len(decoys))) + [expected]
        random.shuffle(choices)
        prompt = (
            f"🧠 **Captcha**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Welcome {user_mention}!\n"
            f"Solve **What is `{num1} + {num2}`?** to confirm you are not a robot.\n\n"
            f"{meta_line}"
        )
    elif mode == "emoji":
        pool = random.sample(EMOJI_POOL, k=6)
        expected = random.choice(pool)
        choices = list(pool)
        random.shuffle(choices)
        prompt = (
            f"🧠 **Captcha — Emoji Match**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Welcome {user_mention}!\n"
            f"Tap the matching emoji button below: **{expected}**\n\n"
            f"{meta_line}"
        )
    elif mode == "word":
        pool = random.sample(WORD_POOL, k=6)
        expected = random.choice(pool)
        choices = list(pool)
        random.shuffle(choices)
        prompt = (
            f"🧠 **Captcha — Word Pick**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Welcome {user_mention}!\n"
            f"Tap the matching word button below: **`{expected}`**\n\n"
            f"{meta_line}"
        )
    else:
        mode = "button"
        expected = "ok"
        choices = ["✅ I am not a robot"]
        prompt = (
            f"🧠 **Captcha**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Welcome {user_mention}!\n"
            f"Press the button below to confirm you are not a robot and unlock chat permissions.\n\n"
            f"{meta_line}"
        )

    cols = 1 if mode == "button" else 3
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, choice in enumerate(choices):
        row.append(InlineKeyboardButton(str(choice), callback_data=f"cap_{user_id}_{idx}"))
        if len(row) == cols:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    return prompt, expected, choices, InlineKeyboardMarkup(buttons)


def format_group_settings_message(cfg: dict) -> str:
    status_label = "Active ✅" if cfg["enabled"] else "Inactive ❌"
    mins = cfg["time_minutes"]
    min_word = "Minute" if mins == 1 else "Minutes"
    penalty_label = cfg["penalty"].capitalize()
    attempts_label = f"{cfg['max_attempts']} (Permanent Mute on fail)"
    del_svc_label = "On" if cfg["delete_service_msg"] else "Off"
    clean_svc_label = "On" if cfg["clean_service"] else "Off"
    lockdown_label = "Locked 🔒" if cfg["lockdown"] else "Open 🔓"

    mode = cfg["mode"]
    if mode == "math":
        mode_line = (
            "🗂 **Mode:** Math\n"
            " └ _The user will have to solve a quick math button to be unmuted._"
        )
    elif mode == "emoji":
        mode_line = (
            "🗂 **Mode:** Emoji\n"
            " └ _The user will have to match the target emoji button to be unmuted._"
        )
    elif mode == "word":
        mode_line = (
            "🗂 **Mode:** Word\n"
            " └ _The user will have to pick the matching word button to be unmuted._"
        )
    else:
        mode_line = (
            "🗂 **Mode:** Button\n"
            " └ _The user will have to press a simple button to be unmuted._\n"
            "_It's a simple but less secure captcha._"
        )

    return (
        f"🧠 **Captcha & Mod — {cfg['title']}** (`{cfg['chat_id']}`)\n"
        "By activating the captcha, when a user enters the group he will not be able to send messages "
        "until he has confirmed that he is not a robot.\n\n"
        "🕑 You can also decide to set a PUNISHMENT down below for those who will not resolve the captcha "
        "within the desired time and whether or not to clear the service message in case of failure.\n\n"
        f"**Status:** {status_label}\n"
        f"🕒 **Time:** {mins} {min_word}\n"
        f"⛔️ **Penalty:** {penalty_label}\n"
        f"🎯 **Max Attempts:** {attempts_label}\n"
        f"{mode_line}\n"
        f"🗑 **Delete service message:** {del_svc_label}\n"
        f"🧹 **Clean join/leave service:** {clean_svc_label}\n"
        f"🔐 **Group Lockdown:** {lockdown_label}"
    )


def build_group_settings_keyboard(cfg: dict) -> InlineKeyboardMarkup:
    gid = cfg["chat_id"]
    toggle_status_btn = InlineKeyboardButton(
        "❌ Disable Captcha" if cfg["enabled"] else "✅ Activate Captcha",
        callback_data=f"cap_cfg_status_{gid}_{0 if cfg['enabled'] else 1}",
    )

    time_buttons = [
        InlineKeyboardButton(
            f"{'• ' if m == cfg['time_minutes'] else ''}{m}m",
            callback_data=f"cap_cfg_time_{gid}_{m}",
        )
        for m in ALLOWED_TIME_MINUTES
    ]

    penalty_buttons = [
        InlineKeyboardButton(
            f"{'• ' if p == cfg['penalty'] else ''}{p.capitalize()}",
            callback_data=f"cap_cfg_pen_{gid}_{p}",
        )
        for p in ALLOWED_PENALTIES
    ]

    attempt_buttons = [
        InlineKeyboardButton(
            f"{'• ' if a == cfg['max_attempts'] else ''}{a} Attempts",
            callback_data=f"cap_cfg_att_{gid}_{a}",
        )
        for a in ALLOWED_ATTEMPTS
    ]

    mode_buttons = [
        InlineKeyboardButton(
            f"{'• ' if m == cfg['mode'] else ''}{m.capitalize()}",
            callback_data=f"cap_cfg_mode_{gid}_{m}",
        )
        for m in ALLOWED_MODES
    ]

    del_svc_btn = InlineKeyboardButton(
        f"🗑 Delete Service Msg: {'On' if cfg['delete_service_msg'] else 'Off'}",
        callback_data=f"cap_cfg_delsvc_{gid}_{0 if cfg['delete_service_msg'] else 1}",
    )

    clean_svc_btn = InlineKeyboardButton(
        f"🧹 Clean Service: {'On' if cfg['clean_service'] else 'Off'}",
        callback_data=f"cap_cfg_cleansvc_{gid}_{0 if cfg['clean_service'] else 1}",
    )

    lockdown_btn = InlineKeyboardButton(
        "🔓 Unlock Chat" if cfg["lockdown"] else "🔒 Lock Chat",
        callback_data=f"cap_cfg_lock_{gid}_{0 if cfg['lockdown'] else 1}",
    )

    return InlineKeyboardMarkup([
        [toggle_status_btn],
        time_buttons[:4],
        time_buttons[4:],
        penalty_buttons,
        attempt_buttons,
        mode_buttons[:2],
        mode_buttons[2:],
        [del_svc_btn, clean_svc_btn],
        [lockdown_btn, InlineKeyboardButton("📜 Mod Logs", callback_data=f"cap_mod_logs_{gid}")],
        [
            InlineKeyboardButton("📋 Groups List", callback_data="cap_priv_list"),
            InlineKeyboardButton("❌ Close", callback_data="cap_adm_close"),
        ],
    ])


async def build_private_groups_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Builds the private-chat group selector menu from MongoDB."""
    groups = await get_all_managed_groups()

    if not groups:
        text = (
            "🧠 **Captcha & Mod Group Selector**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "No groups registered yet.\n\n"
            "Add a group using:\n"
            "`/setcaptcha <chat_id_or_@username> [on|off]`\n"
            "Or send `/captcha` inside a group first so it registers automatically."
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="cap_priv_list"),
                InlineKeyboardButton("❌ Close", callback_data="cap_adm_close"),
            ]
        ])
        return text, kb

    lines = [
        "🧠 **Captcha & Mod Group Selector**\n"
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"Configured groups: **{len(groups)}**\n"
        "Tap a group below to configure captcha & moderation controls:\n",
    ]
    rows: list[list[InlineKeyboardButton]] = []

    for grp in groups[:12]:
        gid = grp["chat_id"]
        title = grp.get("title") or str(gid)
        status_badge = "Active ✅" if grp.get("enabled", True) else "Inactive ❌"
        lock_badge = "🔒" if grp.get("lockdown") else "🔓"
        lines.append(
            f"• **{title}** (`{gid}`) — {status_badge} | `{grp['mode']}` | `{grp['max_attempts']} att` | `{grp['time_minutes']}m` | {lock_badge}"
        )
        rows.append([
            InlineKeyboardButton(
                f"⚙️ {title[:18]} ({status_badge})",
                callback_data=f"cap_cfg_open_{gid}",
            )
        ])

    if len(groups) > 12:
        lines.append(f"\n_Showing first 12 of {len(groups)} groups._")

    rows.append([
        InlineKeyboardButton("🔄 Refresh", callback_data="cap_priv_list"),
        InlineKeyboardButton("❌ Close", callback_data="cap_adm_close"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


async def build_admin_panel(client: Client, chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Builds the in-group pending-captcha list and inline approve/kick buttons."""
    now = time.time()
    cfg = await get_group_config(chat_id)
    records = await get_chat_pending_captchas(chat_id)
    active_records = []

    for rec in records:
        if rec["expires_at"] <= now:
            await apply_punishment_and_cleanup(
                client,
                chat_id,
                rec["user_id"],
                msg_id=rec.get("msg_id"),
                service_msg_id=rec.get("service_msg_id"),
                penalty=rec.get("penalty") or cfg["penalty"],
                delete_service_msg=bool(rec.get("delete_service_msg", cfg["delete_service_msg"])),
            )
        else:
            active_records.append(rec)

    status_label = "Active ✅" if cfg["enabled"] else "Inactive ❌"
    lock_label = "Locked 🔒" if cfg["lockdown"] else "Open 🔓"

    if not active_records:
        text = (
            "🛡️ **Pending Captcha & Mod Status**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"**Status:** {status_label} | **Mode:** `{cfg['mode']}` | **Attempts:** `{cfg['max_attempts']}` | **Time:** `{cfg['time_minutes']}m` | {lock_label}\n"
            "No pending verifications in this chat."
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📜 Mod Logs", callback_data=f"cap_mod_logs_{chat_id}"),
                InlineKeyboardButton("🔄 Refresh", callback_data=f"cap_adm_list_{chat_id}"),
            ],
            [InlineKeyboardButton("❌ Close", callback_data="cap_adm_close")],
        ])
        return text, kb

    lines = [
        "🛡️ **Pending Captcha & Mod Status**\n"
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"**Status:** {status_label} | **Mode:** `{cfg['mode']}` | **Attempts:** `{cfg['max_attempts']}` | **Time:** `{cfg['time_minutes']}m` | {lock_label}",
        f"Active pending users: **{len(active_records)}**\n",
    ]
    rows: list[list[InlineKeyboardButton]] = []

    for rec in active_records[:10]:
        uid = rec["user_id"]
        secs_left = max(1, int(rec["expires_at"] - now))
        att_used = int(rec.get("attempts_used", 0))
        att_max = int(rec.get("max_attempts", cfg["max_attempts"]))
        try:
            u = await client.get_users(uid)
            label_name = u.first_name or str(uid)
            mention = u.mention(label_name)
        except Exception:
            label_name = str(uid)
            mention = f"`{uid}`"

        lines.append(f"• {mention} (`{uid}`) — `{secs_left}s` left | `{att_used}/{att_max}` tries")
        rows.append([
            InlineKeyboardButton(
                f"✅ Approve {label_name[:12]}",
                callback_data=f"cap_adm_approve_{chat_id}_{uid}",
            ),
            InlineKeyboardButton(
                f"👢 Kick {label_name[:12]}",
                callback_data=f"cap_adm_kick_{chat_id}_{uid}",
            ),
        ])

    if len(active_records) > 10:
        lines.append(f"\n_Showing first 10 of {len(active_records)} pending users._")

    rows.append([
        InlineKeyboardButton("📜 Mod Logs", callback_data=f"cap_mod_logs_{chat_id}"),
        InlineKeyboardButton("🔄 Refresh", callback_data=f"cap_adm_list_{chat_id}"),
    ])
    rows.append([InlineKeyboardButton("❌ Close", callback_data="cap_adm_close")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ==========================================
# --- MODERATION COMMANDS (GROUP ADMINS) ---
# ==========================================

@app.on_message(filters.command(["warn"]) & filters.group)
async def cmd_mod_warn(client: Client, message: Message):
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else None
    if not await is_chat_admin(client, chat_id, actor_id):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)

    uid, label, reason = await extract_target_user(client, message, message.command[1:])
    if not uid:
        return await message.reply_text("⚠️ Reply to a user or use `/warn <user_id_or_@username> [reason]`", parse_mode=ParseMode.MARKDOWN)

    await log_mod_action(chat_id, actor_id, "warn", target_user_id=uid, reason=reason)
    warns = await get_user_warnings(chat_id, uid)
    count = len(warns)

    if count >= WARN_LIMIT:
        try:
            await client.restrict_chat_member(chat_id, uid, RESTRICTED_PERMISSIONS)
        except Exception:
            pass
        await clear_user_warnings(chat_id, uid)
        await message.reply_text(
            f"🔇 **{label}** (`{uid}`) reached `{WARN_LIMIT}/{WARN_LIMIT}` warnings and was muted.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        r_text = f" — _{reason}_" if reason else ""
        await message.reply_text(
            f"⚠️ **{label}** (`{uid}`) warned (`{count}/{WARN_LIMIT}`){r_text}.",
            parse_mode=ParseMode.MARKDOWN,
        )


@app.on_message(filters.command(["unwarn"]) & filters.group)
async def cmd_mod_unwarn(client: Client, message: Message):
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else None
    if not await is_chat_admin(client, chat_id, actor_id):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)

    uid, label, _ = await extract_target_user(client, message, message.command[1:])
    if not uid:
        return await message.reply_text("⚠️ Reply to a user or use `/unwarn <user_id_or_@username>`", parse_mode=ParseMode.MARKDOWN)

    removed = await clear_user_warnings(chat_id, uid)
    await log_mod_action(chat_id, actor_id, "unwarn", target_user_id=uid, reason=f"cleared {removed}")
    await message.reply_text(f"✅ Cleared `{removed}` warning(s) for **{label}** (`{uid}`).", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["mute"]) & filters.group)
async def cmd_mod_mute(client: Client, message: Message):
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else None
    if not await is_chat_admin(client, chat_id, actor_id):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)

    uid, label, reason = await extract_target_user(client, message, message.command[1:])
    if not uid:
        return await message.reply_text("⚠️ Reply to a user or use `/mute <user_id_or_@username> [reason]`", parse_mode=ParseMode.MARKDOWN)

    try:
        await client.restrict_chat_member(chat_id, uid, RESTRICTED_PERMISSIONS)
    except Exception as exc:
        return await message.reply_text(f"❌ Failed to mute: `{exc}`", parse_mode=ParseMode.MARKDOWN)

    await log_mod_action(chat_id, actor_id, "mute", target_user_id=uid, reason=reason)
    await message.reply_text(f"🔇 Muted **{label}** (`{uid}`).", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["unmute"]) & filters.group)
async def cmd_mod_unmute(client: Client, message: Message):
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else None
    if not await is_chat_admin(client, chat_id, actor_id):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)

    uid, label, _ = await extract_target_user(client, message, message.command[1:])
    if not uid:
        return await message.reply_text("⚠️ Reply to a user or use `/unmute <user_id_or_@username>`", parse_mode=ParseMode.MARKDOWN)

    try:
        await client.restrict_chat_member(chat_id, uid, UNRESTRICTED_PERMISSIONS)
    except Exception as exc:
        return await message.reply_text(f"❌ Failed to unmute: `{exc}`", parse_mode=ParseMode.MARKDOWN)

    await log_mod_action(chat_id, actor_id, "unmute", target_user_id=uid)
    await message.reply_text(f"🔊 Unmuted **{label}** (`{uid}`).", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["kick"]) & filters.group)
async def cmd_mod_kick(client: Client, message: Message):
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else None
    if not await is_chat_admin(client, chat_id, actor_id):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)

    uid, label, reason = await extract_target_user(client, message, message.command[1:])
    if not uid:
        return await message.reply_text("⚠️ Reply to a user or use `/kick <user_id_or_@username> [reason]`", parse_mode=ParseMode.MARKDOWN)

    try:
        await client.ban_chat_member(chat_id, uid)
        await client.unban_chat_member(chat_id, uid)
    except Exception as exc:
        return await message.reply_text(f"❌ Failed to kick: `{exc}`", parse_mode=ParseMode.MARKDOWN)

    await log_mod_action(chat_id, actor_id, "kick", target_user_id=uid, reason=reason)
    await message.reply_text(f"👢 Kicked **{label}** (`{uid}`).", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["ban"]) & filters.group)
async def cmd_mod_ban(client: Client, message: Message):
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else None
    if not await is_chat_admin(client, chat_id, actor_id):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)

    uid, label, reason = await extract_target_user(client, message, message.command[1:])
    if not uid:
        return await message.reply_text("⚠️ Reply to a user or use `/ban <user_id_or_@username> [reason]`", parse_mode=ParseMode.MARKDOWN)

    try:
        await client.ban_chat_member(chat_id, uid)
    except Exception as exc:
        return await message.reply_text(f"❌ Failed to ban: `{exc}`", parse_mode=ParseMode.MARKDOWN)

    await log_mod_action(chat_id, actor_id, "ban", target_user_id=uid, reason=reason)
    await message.reply_text(f"🔨 Banned **{label}** (`{uid}`).", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["unban"]) & filters.group)
async def cmd_mod_unban(client: Client, message: Message):
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else None
    if not await is_chat_admin(client, chat_id, actor_id):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)

    uid, label, _ = await extract_target_user(client, message, message.command[1:])
    if not uid:
        return await message.reply_text("⚠️ Reply to a user or use `/unban <user_id_or_@username>`", parse_mode=ParseMode.MARKDOWN)

    try:
        await client.unban_chat_member(chat_id, uid)
    except Exception as exc:
        return await message.reply_text(f"❌ Failed to unban: `{exc}`", parse_mode=ParseMode.MARKDOWN)

    await log_mod_action(chat_id, actor_id, "unban", target_user_id=uid)
    await message.reply_text(f"✅ Unbanned **{label}** (`{uid}`).", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["lockdown", "unlock"]) & filters.group)
async def cmd_mod_lockdown(client: Client, message: Message):
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else None
    if not await is_chat_admin(client, chat_id, actor_id):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)

    lock = message.command[0].lower() == "lockdown"
    perms = LOCKDOWN_PERMISSIONS if lock else UNRESTRICTED_PERMISSIONS
    try:
        await client.set_chat_permissions(chat_id, perms)
    except Exception as exc:
        return await message.reply_text(f"❌ Failed to update chat permissions: `{exc}`", parse_mode=ParseMode.MARKDOWN)

    await upsert_group_config(chat_id=chat_id, title=message.chat.title, lockdown=lock, updated_by=actor_id)
    await log_mod_action(chat_id, actor_id, "lockdown_on" if lock else "lockdown_off")
    await message.reply_text(
        "🔒 Group locked for non-admins." if lock else "🔓 Group unlocked for members.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ==========================================
# --- PRIVATE & GROUP CONFIG COMMANDS ---
# ==========================================

@app.on_message(filters.command(["setcaptcha"]) & filters.private)
async def cmd_private_set_captcha(client: Client, message: Message):
    """Private command: /setcaptcha [chat_id_or_@username] [on|off] - Manage group captcha."""
    sender_id = message.from_user.id if message.from_user else None
    args = message.command[1:]

    if not args:
        text, kb = await build_private_groups_panel()
        return await message.reply_text(safe_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    target_raw = args[0]
    state_arg = args[1].lower() if len(args) > 1 else None

    if state_arg not in {None, "on", "off", "enable", "disable", "true", "false", "1", "0"}:
        return await message.reply_text(
            "⚠️ **Usage:** `/setcaptcha <chat_id_or_@username> [on|off]`",
            parse_mode=ParseMode.MARKDOWN,
        )

    chat_id, title_or_err = await resolve_target_group(client, target_raw)
    if chat_id is None:
        return await message.reply_text(
            f"❌ Could not access group `{target_raw}`: `{title_or_err}`",
            parse_mode=ParseMode.MARKDOWN,
        )

    if not await is_chat_admin(client, chat_id, sender_id):
        return await message.reply_text(
            f"⛔ You are not an administrator in **{title_or_err}** (`{chat_id}`).",
            parse_mode=ParseMode.MARKDOWN,
        )

    if state_arg is None:
        cfg = await upsert_group_config(chat_id=chat_id, title=title_or_err, updated_by=sender_id)
    else:
        desired_state = state_arg in {"on", "enable", "true", "1"}
        cfg = await upsert_group_config(
            chat_id=chat_id, title=title_or_err, enabled=desired_state, updated_by=sender_id
        )

    await message.reply_text(
        safe_truncate(format_group_settings_message(cfg)),
        reply_markup=build_group_settings_keyboard(cfg),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command(["captcha"]) & filters.private)
async def cmd_private_captcha_panel(client: Client, message: Message):
    """Private command: /captcha - Opens group selector and settings."""
    text, kb = await build_private_groups_panel()
    await message.reply_text(safe_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["captcha"]) & filters.group)
async def cmd_admin_captcha(client: Client, message: Message):
    """Group admin command: /captcha - Lists pending verifications and registers the group."""
    chat_id = message.chat.id
    sender_id = message.from_user.id if message.from_user else None

    if not await is_chat_admin(client, chat_id, sender_id):
        return await message.reply_text(
            "⛔ Only group administrators can use `/captcha`.",
            parse_mode=ParseMode.MARKDOWN,
        )

    await upsert_group_config(chat_id=chat_id, title=message.chat.title, updated_by=sender_id)
    text, kb = await build_admin_panel(client, chat_id)
    await message.reply_text(safe_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- CALLBACK CONTROLLERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^cap_priv_list$"))
async def cb_private_captcha_list(client: Client, query: CallbackQuery):
    await query.answer("Refreshing groups...")
    text, kb = await build_private_groups_panel()
    await query.message.edit_text(safe_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^cap_cfg_open_(?P<chatid>-?\d+)$"))
async def cb_open_group_settings(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ You must be an admin of that group to manage settings.", show_alert=True)

    title = None
    try:
        chat = await client.get_chat(chat_id)
        title = chat.title
    except Exception:
        pass

    cfg = await get_group_config(chat_id, title=title)
    await query.answer()
    await query.message.edit_text(
        safe_truncate(format_group_settings_message(cfg)),
        reply_markup=build_group_settings_keyboard(cfg),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cap_cfg_status_(?P<chatid>-?\d+)_(?P<state>[01])$"))
async def cb_set_group_status(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    new_enabled = query.matches[0].group("state") == "1"
    if not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await upsert_group_config(chat_id=chat_id, enabled=new_enabled, updated_by=query.from_user.id)
    await query.answer(f"Status: {'Active ✅' if new_enabled else 'Inactive ❌'}", show_alert=True)
    await query.message.edit_text(
        safe_truncate(format_group_settings_message(cfg)),
        reply_markup=build_group_settings_keyboard(cfg),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cap_cfg_time_(?P<chatid>-?\d+)_(?P<mins>\d+)$"))
async def cb_set_group_time(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    mins = int(query.matches[0].group("mins"))
    if mins not in ALLOWED_TIME_MINUTES:
        return await query.answer("Invalid time value.", show_alert=True)
    if not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await upsert_group_config(chat_id=chat_id, time_minutes=mins, updated_by=query.from_user.id)
    await query.answer(f"Time set to {mins} Minutes", show_alert=True)
    await query.message.edit_text(
        safe_truncate(format_group_settings_message(cfg)),
        reply_markup=build_group_settings_keyboard(cfg),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cap_cfg_pen_(?P<chatid>-?\d+)_(?P<penalty>mute|kick|ban)$"))
async def cb_set_group_penalty(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    penalty = query.matches[0].group("penalty")
    if not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await upsert_group_config(chat_id=chat_id, penalty=penalty, updated_by=query.from_user.id)
    await query.answer(f"Penalty set to {penalty.capitalize()}", show_alert=True)
    await query.message.edit_text(
        safe_truncate(format_group_settings_message(cfg)),
        reply_markup=build_group_settings_keyboard(cfg),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cap_cfg_att_(?P<chatid>-?\d+)_(?P<attempts>\d+)$"))
async def cb_set_group_attempts(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    attempts = int(query.matches[0].group("attempts"))
    if attempts not in ALLOWED_ATTEMPTS:
        return await query.answer("Attempts must be 3 or 5.", show_alert=True)
    if not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await upsert_group_config(chat_id=chat_id, max_attempts=attempts, updated_by=query.from_user.id)
    await query.answer(f"Max attempts set to {attempts}", show_alert=True)
    await query.message.edit_text(
        safe_truncate(format_group_settings_message(cfg)),
        reply_markup=build_group_settings_keyboard(cfg),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cap_cfg_mode_(?P<chatid>-?\d+)_(?P<mode>button|math|emoji|word)$"))
async def cb_set_group_mode(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    mode = query.matches[0].group("mode")
    if not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await upsert_group_config(chat_id=chat_id, mode=mode, updated_by=query.from_user.id)
    await query.answer(f"Mode set to {mode.capitalize()}", show_alert=True)
    await query.message.edit_text(
        safe_truncate(format_group_settings_message(cfg)),
        reply_markup=build_group_settings_keyboard(cfg),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cap_cfg_delsvc_(?P<chatid>-?\d+)_(?P<state>[01])$"))
async def cb_set_group_del_svc(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    del_svc = query.matches[0].group("state") == "1"
    if not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await upsert_group_config(chat_id=chat_id, delete_service_msg=del_svc, updated_by=query.from_user.id)
    await query.answer(f"Delete service message: {'On' if del_svc else 'Off'}", show_alert=True)
    await query.message.edit_text(
        safe_truncate(format_group_settings_message(cfg)),
        reply_markup=build_group_settings_keyboard(cfg),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cap_cfg_cleansvc_(?P<chatid>-?\d+)_(?P<state>[01])$"))
async def cb_set_group_clean_svc(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    clean_svc = query.matches[0].group("state") == "1"
    if not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await upsert_group_config(chat_id=chat_id, clean_service=clean_svc, updated_by=query.from_user.id)
    await query.answer(f"Clean join/leave service: {'On' if clean_svc else 'Off'}", show_alert=True)
    await query.message.edit_text(
        safe_truncate(format_group_settings_message(cfg)),
        reply_markup=build_group_settings_keyboard(cfg),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cap_cfg_lock_(?P<chatid>-?\d+)_(?P<state>[01])$"))
async def cb_set_group_lockdown(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    lock = query.matches[0].group("state") == "1"
    if not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    try:
        await client.set_chat_permissions(chat_id, LOCKDOWN_PERMISSIONS if lock else UNRESTRICTED_PERMISSIONS)
    except Exception as exc:
        return await query.answer(f"Permission error: {str(exc)[:140]}", show_alert=True)

    cfg = await upsert_group_config(chat_id=chat_id, lockdown=lock, updated_by=query.from_user.id)
    await log_mod_action(chat_id, query.from_user.id, "lockdown_on" if lock else "lockdown_off")
    await query.answer("🔒 Chat locked" if lock else "🔓 Chat unlocked", show_alert=True)
    await query.message.edit_text(
        safe_truncate(format_group_settings_message(cfg)),
        reply_markup=build_group_settings_keyboard(cfg),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cap_mod_logs_(?P<chatid>-?\d+)$"))
async def cb_view_mod_logs(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    await query.answer("Loading mod logs...")
    logs = await get_recent_mod_logs(chat_id, limit=8)
    lines = [f"📜 **Recent Mod Logs** (`{chat_id}`)", "━━━━━━━━━━━━━━━━━━━━━━"]
    if not logs:
        lines.append("_No moderation actions logged yet._")
    else:
        for entry in logs:
            act = entry.get("action", "action")
            tid = entry.get("target_user_id")
            rsn = entry.get("reason") or ""
            target_str = f" -> `{tid}`" if tid else ""
            reason_str = f" _({rsn})_" if rsn else ""
            lines.append(f"• `{act}`{target_str}{reason_str}")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Group Settings", callback_data=f"cap_cfg_open_{chat_id}")],
        [InlineKeyboardButton("❌ Close", callback_data="cap_adm_close")],
    ])
    await query.message.edit_text(safe_truncate("\n".join(lines)), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^cap_adm_list_(?P<chatid>-?\d+)$"))
async def cb_admin_captcha_list(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    await query.answer("Refreshing pending list...")
    text, kb = await build_admin_panel(client, chat_id)
    await query.message.edit_text(safe_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(
    filters.regex(r"^cap_adm_(?P<action>approve|kick)_(?P<chatid>-?\d+)_(?P<userid>\d+)$")
)
async def cb_admin_captcha_action(client: Client, query: CallbackQuery):
    action = query.matches[0].group("action")
    chat_id = int(query.matches[0].group("chatid"))
    target_user_id = int(query.matches[0].group("userid"))

    if not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    record = await get_pending_captcha(chat_id, target_user_id)
    prompt_msg_id = record.get("msg_id") if record else None
    service_msg_id = record.get("service_msg_id") if record else None

    if action == "approve":
        await approve_user_captcha(client, chat_id, target_user_id, prompt_msg_id, service_msg_id)
        await log_mod_action(chat_id, query.from_user.id, "captcha_approve", target_user_id=target_user_id)
        await query.answer(f"✅ Approved user {target_user_id}.", show_alert=True)
    else:
        grp_cfg = await get_group_config(chat_id)
        await apply_punishment_and_cleanup(
            client,
            chat_id,
            target_user_id,
            msg_id=prompt_msg_id,
            service_msg_id=service_msg_id,
            penalty="kick",
            delete_service_msg=(
                bool(record.get("delete_service_msg", grp_cfg["delete_service_msg"]))
                if record
                else grp_cfg["delete_service_msg"]
            ),
        )
        await log_mod_action(chat_id, query.from_user.id, "captcha_kick", target_user_id=target_user_id)
        await query.answer(f"👢 Kicked user {target_user_id}.", show_alert=True)

    text, kb = await build_admin_panel(client, chat_id)
    await query.message.edit_text(safe_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^cap_adm_close$"))
async def cb_admin_captcha_close(client: Client, query: CallbackQuery):
    chat_id = query.message.chat.id if query.message and query.message.chat else 0
    if chat_id and chat_id < 0 and not await is_chat_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    await query.answer("Closed")
    await query.message.delete()


# ==========================================
# --- JOIN / LEAVE & CAPTCHA SOLVE ---
# ==========================================

@app.on_message(filters.left_chat_member)
async def handle_left_member(client: Client, message: Message):
    """Optionally deletes member-left service messages when clean_service is enabled."""
    cfg = await get_group_config(message.chat.id, title=message.chat.title)
    if cfg.get("clean_service"):
        await _delete_message_safe(client, message.chat.id, message.id)


@app.on_message(filters.new_chat_members)
async def handle_new_member(client: Client, message: Message):
    """Restricts joining members when enabled for the group, saves state, and starts timer."""
    chat_id = message.chat.id
    cfg = await get_group_config(chat_id, title=message.chat.title)

    if cfg.get("clean_service") and not cfg.get("delete_service_msg"):
        await _delete_message_safe(client, chat_id, message.id)

    if not cfg["enabled"]:
        return

    me = await client.get_me()
    timeout_seconds = int(cfg["time_minutes"]) * 60
    penalty = cfg["penalty"]
    mode = cfg["mode"]
    max_attempts = int(cfg.get("max_attempts", 3))
    delete_service_msg = bool(cfg["delete_service_msg"])

    for member in message.new_chat_members:
        if member.id == me.id:
            continue

        user_id = member.id
        user_mention = member.mention(member.first_name)

        try:
            await client.restrict_chat_member(chat_id, user_id, RESTRICTED_PERMISSIONS)
        except Exception:
            continue

        prompt_text, expected_val, choices, keyboard = _build_captcha_challenge(
            mode=mode,
            user_id=user_id,
            user_mention=user_mention,
            cfg=cfg,
        )

        sent_msg = await message.reply_text(
            safe_truncate(prompt_text),
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )

        expires_at = time.time() + timeout_seconds
        await upsert_pending_captcha(
            chat_id=chat_id,
            user_id=user_id,
            msg_id=sent_msg.id,
            mode=mode,
            expected_value=expected_val,
            choices=choices,
            expires_at=expires_at,
            max_attempts=max_attempts,
            attempts_used=0,
            service_msg_id=message.id,
            penalty=penalty,
            delete_service_msg=delete_service_msg,
        )
        schedule_captcha_timer(client, chat_id, user_id, sent_msg.id, expires_at)


@app.on_callback_query(filters.regex(r"^cap_(?P<userid>\d+)_(?P<choice_idx>\d+)$"))
async def cb_solve_captcha(client: Client, query: CallbackQuery):
    match = query.matches[0]
    target_user_id = int(match.group("userid"))
    choice_idx = int(match.group("choice_idx"))
    clicker_id = query.from_user.id

    if clicker_id != target_user_id:
        return await query.answer("❌ This verification puzzle is not for you!", show_alert=True)

    chat_id = query.message.chat.id
    record = await get_pending_captcha(chat_id, target_user_id)

    if not record:
        await query.answer("⚠️ Verification expired or already completed.", show_alert=True)
        await _delete_message_safe(client, chat_id, query.message.id)
        return

    if time.time() > record["expires_at"]:
        grp_cfg = await get_group_config(chat_id)
        penalty = record.get("penalty") or grp_cfg["penalty"]
        del_svc = bool(record.get("delete_service_msg", grp_cfg["delete_service_msg"]))
        await query.answer(f"⏱️ Time expired! Applying {penalty}.", show_alert=True)
        await apply_punishment_and_cleanup(
            client,
            chat_id,
            target_user_id,
            msg_id=record["msg_id"],
            service_msg_id=record.get("service_msg_id"),
            penalty=penalty,
            delete_service_msg=del_svc,
        )
        return

    choices = record.get("choices") or []
    expected_val = str(record.get("expected_value", ""))
    picked_val = str(choices[choice_idx]) if 0 <= choice_idx < len(choices) else ""

    if picked_val == expected_val:
        await delete_pending_captcha(chat_id, target_user_id)
        _cancel_timer(chat_id, target_user_id)

        try:
            await client.restrict_chat_member(chat_id, target_user_id, UNRESTRICTED_PERMISSIONS)
        except Exception:
            pass

        await query.answer("✅ Verification successful! Welcome to the chat.", show_alert=True)
        await query.message.edit_text(
            f"✅ **Verification Passed!**\n"
            f"Welcome {query.from_user.mention}, you are now verified and can send messages.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    updated = await increment_captcha_attempts(chat_id, target_user_id)
    max_attempts = int((updated or record).get("max_attempts", 3))
    attempts_used = int((updated or record).get("attempts_used", 1))

    if attempts_used >= max_attempts:
        del_svc = bool(record.get("delete_service_msg", False))
        await enforce_permanent_mute_and_cleanup(
            client,
            chat_id,
            target_user_id,
            msg_id=record.get("msg_id"),
            service_msg_id=record.get("service_msg_id"),
            delete_service_msg=del_svc,
        )
        await log_mod_action(
            chat_id,
            actor_id=None,
            action="captcha_perm_mute",
            target_user_id=target_user_id,
            reason=f"failed {max_attempts} attempts",
        )
        await query.answer(
            f"🔇 Too many wrong attempts ({max_attempts}/{max_attempts}). You are muted forever.",
            show_alert=True,
        )
        try:
            await query.message.edit_text(
                f"🔇 **Permanently Muted**\n"
                f"{query.from_user.mention} failed all `{max_attempts}` captcha attempts and remains muted.",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
    else:
        left = max_attempts - attempts_used
        await query.answer(
            f"❌ Incorrect choice! {left} attempt(s) remaining before permanent mute.",
            show_alert=True,
        )


asyncio.get_event_loop().create_task(recover_pending_captchas(app))
