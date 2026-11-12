import asyncio
import io
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain APY_TOKEN

# --- CONFIGURATION & BASE URL ---
APY_BASE = "https://api.eu.apyhub.com/apyhub"

def get_apy_token() -> str:
    """Retrieves the ApyHub token from config safely."""
    return getattr(Config, "APY_HUB_TOKEN", None)


# --- APYHUB ASYNC JOB HELPERS ---

async def submit_gif_job(video_url: str, size: str = None, speed: str = None, duration: str = None) -> str:
    """Submits a video URL to start an async GIF generation job and returns the job_id."""
    token = get_apy_token()
    if not token:
        return None

    endpoint = f"{APY_BASE}/generate-gif-from-video/url-to-json"
    headers = {"apy-token": token, "Content-Type": "application/json"}
    
    payload = {"video_url": video_url.strip()}
    if size: payload["size"] = size
    if speed: payload["speed"] = speed
    if duration: payload["duration"] = duration

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url=endpoint, json=payload, headers=headers, timeout=20.0)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("job_id")
            print(f"Submit GIF Job Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Submit GIF Job Exception: {e}")
        return None


async def check_gif_job_status(job_id: str) -> dict:
    """Polls the status of the GIF conversion job by job ID."""
    token = get_apy_token()
    if not token:
        return {"status": "failed", "message": "Missing API token"}

    endpoint = f"{APY_BASE}/generate-gif-from-video/jobs/{job_id}"
    headers = {"apy-token": token}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url=endpoint, headers=headers, timeout=15.0)
            if resp.status_code == 200:
                res_data = resp.json()
                return res_data.get("data", {})
            print(f"Check Job Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Check Job Exception: {e}")
        return {"status": "pending", "message": "Polling error or timeout"}


# --- COMMAND HANDLER ---

@app.on_message(filters.command(["videotogif", "gifjob"]))
async def cmd_video_to_gif(client: Client, message: Message):
    """Command: /videotogif <public_video_url>"""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/videotogif <public_video_url>`\n\n"
            "_Example:_ `/videotogif https://assets.apyhub.com/samples/sample.mp4`",
            parse_mode=ParseMode.MARKDOWN
        )

    video_url = args[1].strip()
    status_msg = await message.reply_text("🎬 Enqueuing video-to-GIF conversion job via ApyHub...")

    # Step 1: Submit the job
    job_id = await submit_gif_job(video_url)
    if not job_id:
        return await status_msg.edit_text("❌ Failed to submit GIF generation job. Check your API token or URL format.")

    await status_msg.edit_text(f"⏳ Job enqueued (`{job_id}`). Processing video into GIF...")

    # Step 2: Poll for completion (up to 30 attempts, 2 seconds apart)
    max_attempts = 30
    gif_result_url = None

    for attempt in range(1, max_attempts + 1):
        await asyncio.sleep(2.0)  # Poll every 2 seconds (safe for rate limits)
        
        job_data = await check_gif_job_status(job_id)
        status = job_data.get("status", "pending")

        if status == "successful":
            gif_result_url = job_data.get("url")
            break
        elif status == "failed":
            error_msg = job_data.get("message", "Unknown worker failure")
            return await status_msg.edit_text(f"❌ GIF generation failed: `{error_msg}`", parse_mode=ParseMode.MARKDOWN)
        
        # Optional: Update status on periodic intervals
        if attempt % 5 == 0:
            await status_msg.edit_text(f"⏳ Processing... (Attempt {attempt}/{max_attempts})")

    if not gif_result_url:
        return await status_msg.edit_text("⏱️ Job timed out while waiting for the GIF to render. Please try again later.")

    await status_msg.edit_text("⬇️ Downloading generated GIF and sending to Telegram...")

    # Step 3: Download resulting GIF bytes and send to user
    async with httpx.AsyncClient(follow_redirects=True) as http_client:
        try:
            gif_resp = await http_client.get(gif_result_url, timeout=30.0)
            if gif_resp.status_code != 200:
                return await status_msg.edit_text(f"🔗 **GIF Ready!**\n\nDownload Link: {gif_result_url}")

            gif_bytes = io.BytesIO(gif_resp.content)
            gif_bytes.name = "animation.gif"

            await message.reply_animation(
                animation=gif_bytes,
                caption="🎉 **Animated GIF Generated Successfully!**\n_Powered by ApyHub Video to GIF Suite_",
                parse_mode=ParseMode.MARKDOWN
            )
            await status_msg.delete()

        except Exception as e:
            await status_msg.edit_text(f"🔗 **GIF Generated Successfully!**\n\nDownload Link: {gif_result_url}")


@app.on_message(filters.command("gifhelp"))
async def cmd_gif_help(client: Client, message: Message):
    """Command: /gifhelp"""
    help_text = (
        "📖 **ApyHub Video-to-GIF Bot — Guide**\n\n"
        "• `/videotogif <url>` — Convert any public MP4/MOV URL into an animated GIF.\n\n"
        "_Utilizes ApyHub's asynchronous background job & polling architecture._"
    )
    await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
