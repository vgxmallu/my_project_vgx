import os
import time
from urllib.parse import urlencode
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.errors import MessageNotModified
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from vgx import app

# ==========================================
# ⚙️ CONFIG & MONGODB SETUP
# ==========================================
SPOTIFY_CLIENT_ID = getattr(Config, "SPOTIPY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = getattr(Config, "SPOTIPY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = getattr(Config, "SPOTIFY_REDIRECT_URI")

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_SCOPES = "user-read-playback-state user-modify-playback-state"

MONGO_URL = getattr(Config, "MONGO_URL", None) or os.getenv("MONGO_URI", "mongodb://localhost:27017")
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client[getattr(Config, "DB_NAME", "GojoBotDB")]
spotify_tokens_col = db["spotify_tokens"]


# ==========================================
# 🔐 OAUTH & TOKEN MANAGEMENT
# ==========================================
def build_spotify_auth_url(user_id: int) -> str:
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SPOTIFY_SCOPES,
        "state": str(user_id),
    }
    return f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str):
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(SPOTIFY_TOKEN_URL, data=payload) as resp:
            data = await resp.json()
            return resp.status, data


async def get_valid_access_token(user_id: int):
    doc = await spotify_tokens_col.find_one({"_id": user_id})
    if not doc or not doc.get("refresh_token"):
        return None

    now = time.time()
    # Refresh if expired or expiring within 60 seconds
    if now >= doc.get("expires_at", 0) - 60:
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": doc["refresh_token"],
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(SPOTIFY_TOKEN_URL, data=payload) as resp:
                if resp.status != 200:
                    return None
                token_data = await resp.json()

        new_access = token_data.get("access_token")
        new_refresh = token_data.get("refresh_token") or doc["refresh_token"]
        expires_in = int(token_data.get("expires_in", 3600))
        new_expiry = time.time() + expires_in

        await spotify_tokens_col.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "access_token": new_access,
                    "refresh_token": new_refresh,
                    "expires_at": new_expiry,
                }
            },
        )
        return new_access

    return doc.get("access_token")


# ==========================================
# 🎵 SPOTIFY PLAYER API HELPERS
# ==========================================
async def spotify_api(user_id: int, method: str, endpoint: str, params: dict = None, json_body: dict = None):
    token = await get_valid_access_token(user_id)
    if not token:
        return None, {"error": "Not linked. Use /spauth first."}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"{SPOTIFY_API_BASE}{endpoint}"
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, headers=headers, params=params, json=json_body) as resp:
            status = resp.status
            if status == 204:
                return 204, {"ok": True}
            try:
                data = await resp.json()
            except Exception:
                data = {"raw": await resp.text()}
            return status, data


def format_ms(ms: int) -> str:
    if not ms or ms < 0:
        return "0:00"
    total_sec = ms // 1000
    mins, secs = divmod(total_sec, 60)
    return f"{mins}:{secs:02d}"


async def build_player_view(user_id: int, notice: str = ""):
    status, data = await spotify_api(user_id, "GET", "/me/player")
    if status is None:
        return (
            "🎧 **Spotify Player**\n━━━━━━━━━━━━━━━━━━━━\n"
            "❌ Your Spotify account isn't linked yet.\n"
            "Use `/spauth` to connect your account.",
            None,
        )

    if status != 200 or not data or not data.get("item"):
        text = (
            "🎧 **Spotify Player**\n━━━━━━━━━━━━━━━━━━━━\n"
            "⏸ **Nothing currently playing** or no active Spotify device found.\n"
            "Open Spotify on a device and tap **Refresh** or **Devices**."
        )
        if notice:
            text += f"\n\n📌 {notice}"
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f"sp_refresh_{user_id}"),
                InlineKeyboardButton("📱 Devices", callback_data=f"sp_devices_{user_id}"),
            ],
            [InlineKeyboardButton("✖️ Close", callback_data=f"sp_close_{user_id}")],
        ])
        return text, kb

    item = data["item"]
    title = item.get("name", "Unknown Track")
    duration_ms = item.get("duration_ms", 0)
    progress_ms = data.get("progress_ms") or 0
    is_playing = data.get("is_playing", False)
    shuffle_on = data.get("shuffle_state", False)
    repeat_state = data.get("repeat_state", "off")
    device = data.get("device") or {}

    if "artists" in item and item["artists"]:
        subtitle = ", ".join(a.get("name", "") for a in item["artists"] if a.get("name"))
    else:
        subtitle = (item.get("show") or {}).get("name", "Episode")

    state_icon = "▶️ Playing" if is_playing else "⏸ Paused"
    shuffle_label = "🔀 Shuffle: ON" if shuffle_on else "➡️ Shuffle: OFF"
    repeat_label = f"🔁 Repeat: {repeat_state.upper()}"
    device_name = device.get("name") or "Unknown Device"
    device_type = device.get("type") or "device"
    vol = device.get("volume_percent")
    vol_str = f" ({vol}%)" if vol is not None else ""

    text = (
        f"🎧 **Spotify Player — {state_icon}**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎶 **Track:** `{title}`\n"
        f"👤 **Artist/Show:** `{subtitle}`\n"
        f"⏱ **Progress:** `{format_ms(progress_ms)} / {format_ms(duration_ms)}`\n"
        f"📱 **Device:** `{device_name}` ({device_type}){vol_str}\n"
        f"⚙️ **Mode:** `{shuffle_label}` • `{repeat_label}`"
    )
    if notice:
        text += f"\n\n📌 {notice}"

    play_pause_btn = (
        InlineKeyboardButton("⏸ Pause", callback_data=f"sp_pause_{user_id}")
        if is_playing
        else InlineKeyboardButton("▶️ Resume", callback_data=f"sp_play_{user_id}")
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏮ Prev", callback_data=f"sp_prev_{user_id}"),
            play_pause_btn,
            InlineKeyboardButton("⏭ Next", callback_data=f"sp_next_{user_id}"),
        ],
        [
            InlineKeyboardButton("⏪ -15s", callback_data=f"sp_seekm_{user_id}"),
            InlineKeyboardButton("⏩ +15s", callback_data=f"sp_seekp_{user_id}"),
            InlineKeyboardButton("📜 Queue", callback_data=f"sp_queue_{user_id}"),
        ],
        [
            InlineKeyboardButton(shuffle_label, callback_data=f"sp_shuffle_{user_id}"),
            InlineKeyboardButton(repeat_label, callback_data=f"sp_repeat_{user_id}"),
        ],
        [
            InlineKeyboardButton("📱 Devices", callback_data=f"sp_devices_{user_id}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"sp_refresh_{user_id}"),
        ],
        [InlineKeyboardButton("✖️ Close", callback_data=f"sp_close_{user_id}")],
    ])
    return text, kb


# ==========================================
# ⚡ COMMANDS
# ==========================================
@app.on_message(filters.command("spauth"))
async def cmd_spauth(client: Client, message: Message):
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return await message.reply_text("❌ `SPOTIFY_CLIENT_ID` or `SPOTIFY_CLIENT_SECRET` is missing.")

    if len(message.command) > 1 and message.command[1] != "link":
        auth_code = message.command[1].strip()
        status, token_data = await exchange_code_for_tokens(auth_code)
        if status != 200 or not token_data.get("access_token"):
            err = token_data.get("error_description") or token_data.get("error") or f"HTTP {status}"
            return await message.reply_text(f"❌ Token exchange failed: `{err}`")

        expires_in = int(token_data.get("expires_in", 3600))
        await spotify_tokens_col.update_one(
            {"_id": message.from_user.id},
            {
                "$set": {
                    "access_token": token_data["access_token"],
                    "refresh_token": token_data.get("refresh_token"),
                    "expires_at": time.time() + expires_in,
                }
            },
            upsert=True,
        )
        return await message.reply_text("✅ **Spotify Connected!** Use `/spplayer` or `/spqueue` now.")

    auth_url = build_spotify_auth_url(message.from_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Authorize Spotify", url=auth_url)],
    ])
    await message.reply_text(
        "🔐 **Link Your Spotify Account**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "1. Tap **Authorize Spotify** and approve playback permissions.\n"
        "2. Copy the `code` query parameter from your redirect URL.\n"
        "3. Send `/spauth <your_code>` here.",
        reply_markup=kb,
        disable_web_page_preview=True,
    )


@app.on_message(filters.command(["spplayer", "nowplaying"]))
async def cmd_spplayer(client: Client, message: Message):
    uid = message.from_user.id
    text, kb = await build_player_view(uid)
    await message.reply_text(text, reply_markup=kb)


@app.on_message(filters.command("spqueue"))
async def cmd_spqueue(client: Client, message: Message):
    uid = message.from_user.id
    status, data = await spotify_api(uid, "GET", "/me/player/queue")
    if status is None:
        return await message.reply_text("❌ Link Spotify first with `/spauth`.")
    if status != 200 or not isinstance(data, dict):
        return await message.reply_text(f"❌ Could not load queue (`HTTP {status}`).")

    curr = data.get("currently_playing") or {}
    queue_items = data.get("queue") or []

    lines = ["📜 **Spotify Queue**\n━━━━━━━━━━━━━━━━━━━━"]
    if curr.get("name"):
        c_artists = ", ".join(a.get("name", "") for a in curr.get("artists", []) if a.get("name"))
        lines.append(f"▶️ **Now:** `{curr['name']}`" + (f" — *{c_artists}*" if c_artists else ""))

    if queue_items:
        lines.append("\n**Up Next:**")
        for idx, track in enumerate(queue_items[:8], 1):
            t_name = track.get("name", "Unknown")
            t_artists = ", ".join(a.get("name", "") for a in track.get("artists", []) if a.get("name"))
            lines.append(f"{idx}. `{t_name}`" + (f" — {t_artists}" if t_artists else ""))
    else:
        lines.append("\n📭 *Queue is empty.*")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎧 Back to Player", callback_data=f"sp_refresh_{uid}")],
        [InlineKeyboardButton("✖️ Close", callback_data=f"sp_close_{uid}")],
    ])
    await message.reply_text("\n".join(lines), reply_markup=kb)


# ==========================================
# 🎛️ CALLBACK ROUTER (PLAYBACK & DEVICES)
# ==========================================
@app.on_callback_query(
    filters.regex(r"^sp_(refresh|play|pause|next|prev|seekm|seekp|shuffle|repeat|queue|devices|close)_(\d+)$")
)
async def sp_callback_router(client: Client, query: CallbackQuery):
    action = query.matches[0].group(1)
    owner_uid = int(query.matches[0].group(2))

    if query.from_user.id != owner_uid:
        return await query.answer("❌ This player belongs to another user.", show_alert=True)

    if action == "close":
        try:
            await query.message.delete()
        except Exception:
            await query.message.edit_text("✖️ Closed.")
        return await query.answer()

    notice = ""

    if action == "play":
        st, _ = await spotify_api(owner_uid, "PUT", "/me/player/play")
        notice = "Resumed playback." if st in (200, 204) else f"Play failed ({st})."

    elif action == "pause":
        st, _ = await spotify_api(owner_uid, "PUT", "/me/player/pause")
        notice = "Paused playback." if st in (200, 204) else f"Pause failed ({st})."

    elif action == "next":
        st, _ = await spotify_api(owner_uid, "POST", "/me/player/next")
        notice = "Skipped to next track." if st in (200, 204) else f"Next failed ({st})."

    elif action == "prev":
        st, _ = await spotify_api(owner_uid, "POST", "/me/player/previous")
        notice = "Skipped to previous track." if st in (200, 204) else f"Previous failed ({st})."

    elif action in ("seekm", "seekp"):
        st, state = await spotify_api(owner_uid, "GET", "/me/player")
        if st == 200 and isinstance(state, dict):
            curr_ms = state.get("progress_ms") or 0
            dur_ms = (state.get("item") or {}).get("duration_ms") or 0
            delta = -15000 if action == "seekm" else 15000
            target_ms = max(0, min(dur_ms if dur_ms > 0 else curr_ms + delta, curr_ms + delta))
            seek_st, _ = await spotify_api(owner_uid, "PUT", "/me/player/seek", params={"position_ms": target_ms})
            notice = f"Seeked to {format_ms(target_ms)}." if seek_st in (200, 204) else f"Seek failed ({seek_st})."
        else:
            notice = "No active track to seek."

    elif action == "shuffle":
        st, state = await spotify_api(owner_uid, "GET", "/me/player")
        current_shuffle = bool((state or {}).get("shuffle_state", False))
        new_shuffle = str(not current_shuffle).lower()
        sh_st, _ = await spotify_api(owner_uid, "PUT", "/me/player/shuffle", params={"state": new_shuffle})
        notice = f"Shuffle set to {new_shuffle.upper()}." if sh_st in (200, 204) else f"Shuffle failed ({sh_st})."

    elif action == "repeat":
        st, state = await spotify_api(owner_uid, "GET", "/me/player")
        curr_rep = (state or {}).get("repeat_state", "off")
        cycle = {"off": "context", "context": "track", "track": "off"}
        next_rep = cycle.get(curr_rep, "off")
        rep_st, _ = await spotify_api(owner_uid, "PUT", "/me/player/repeat", params={"state": next_rep})
        notice = f"Repeat set to {next_rep.upper()}." if rep_st in (200, 204) else f"Repeat failed ({rep_st})."

    elif action == "queue":
        st, qdata = await spotify_api(owner_uid, "GET", "/me/player/queue")
        if st == 200 and isinstance(qdata, dict):
            q_list = qdata.get("queue") or []
            if q_list:
                top_three = ", ".join(t.get("name", "?") for t in q_list[:3])
                notice = f"Queue ({len(q_list)}): {top_three}"
            else:
                notice = "Queue is currently empty."
        else:
            notice = f"Queue fetch failed ({st})."

    elif action == "devices":
        st, ddata = await spotify_api(owner_uid, "GET", "/me/player/devices")
        devices = (ddata or {}).get("devices") or [] if st == 200 else []
        if not devices:
            text = (
                "📱 **Available Spotify Devices**\n━━━━━━━━━━━━━━━━━━━━\n"
                "No devices found. Open Spotify on your phone, PC, or web player."
            )
        else:
            lines = ["📱 **Available Spotify Devices**\n━━━━━━━━━━━━━━━━━━━━\nTap a device to transfer playback:"]
            btn_rows = []
            for dev in devices[:6]:
                dev_id = dev.get("id")
                dev_name = dev.get("name", "Device")
                active_tag = "🟢 " if dev.get("is_active") else "⚪ "
                lines.append(f"{active_tag}`{dev_name}` ({dev.get('type', 'device')})")
                if dev_id:
                    btn_rows.append([
                        InlineKeyboardButton(f"📲 Transfer → {dev_name[:22]}", callback_data=f"spdev_{dev_id}_{owner_uid}")
                    ])
            btn_rows.append([InlineKeyboardButton("🔙 Back to Player", callback_data=f"sp_refresh_{owner_uid}")])
            try:
                await query.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btn_rows))
            except MessageNotModified:
                pass
            return await query.answer()

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Player", callback_data=f"sp_refresh_{owner_uid}")],
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb)
        except MessageNotModified:
            pass
        return await query.answer()

    text, kb = await build_player_view(owner_uid, notice=notice)
    try:
        await query.message.edit_text(text, reply_markup=kb)
    except MessageNotModified:
        pass
    await query.answer(notice or "Updated!")


@app.on_callback_query(filters.regex(r"^spdev_([^_]+)_(\d+)$"))
async def sp_transfer_device_callback(client: Client, query: CallbackQuery):
    device_id = query.matches[0].group(1)
    owner_uid = int(query.matches[0].group(2))

    if query.from_user.id != owner_uid:
        return await query.answer("❌ This player belongs to another user.", show_alert=True)

    st, _ = await spotify_api(
        owner_uid,
        "PUT",
        "/me/player",
        json_body={"device_ids": [device_id], "play": True},
    )
    notice = "Transferred playback to device!" if st in (200, 204) else f"Transfer failed ({st})."
    text, kb = await build_player_view(owner_uid, notice=notice)
    try:
        await query.message.edit_text(text, reply_markup=kb)
    except MessageNotModified:
        pass
    await query.answer(notice, show_alert=False)
