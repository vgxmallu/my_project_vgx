import os
import io
import asyncio
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


# --- APYHUB ASYNC COMPRESSION HELPERS ---

async def submit_compress_job(file_path: str, compression_percentage: int = 50) -> str:
    """Submits a video file to enqueue an async compression job and returns the job_id."""
    token = get_apy_token()
    if not token:
        return None

    endpoint = f"{APY_BASE}/compress-video-job/file-to-json"
    headers = {"apy-token": token}

    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"video": (os.path.basename(file_path), f)}
                data = {"compression_percentage": str(compression_percentage)}
                
                resp = await client.post(url=endpoint, headers=headers, files=files, data=data, timeout=60.0)
                if resp.status_code == 200:
                    res_data = resp.json()
                    return res_data.get("job_id")  # Returned directly at top level
                print(f"Submit Compression Job Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Submit Compression Job Exception: {e}")
        return None


async def check_compress_job_status(job_id: str) -> dict:
    """Polls the status of the compression job by job ID."""
    token = get_apy_token()
    if not token:
        return {"status": "failed", "message": "Missing API token"}

    endpoint = f"{APY_BASE}/compress-video-job/jobs/{job_id}"
    headers = {"apy-token": token}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url=endpoint, headers=headers, timeout=15.0)
            if resp.status_code == 200:
                res_json = resp.json()
                return res_json.get("data", {})  # Status info is nested inside data field
            print(f"Check Compression Job Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Check Compression Job Exception: {e}")
        return {"status": "pending", "message": "Polling network error or timeout"}


# --- COMMAND HANDLER ---

@app.on_message(filters.command(["compressvideo", "compress"]) & filters.reply)
async def cmd_compress_video(client: Client, message: Message):
    """Command: /compressvideo (Reply to a video file)"""
    target = message.reply_to_message
    if not target.video and not target.document:
        return await message.reply_text("⚠️ Please reply to a valid video file or document with `/compressvideo`.")

    status_msg = await message.reply_text("📦 Downloading video for compression...")

    try:
        # Download media locally
        path = await client.download_media(target)
    except Exception as e:
        return await status_msg.edit_text(f"❌ Failed to download video: `{str(e)}`", parse_mode=ParseMode.MARKDOWN)

    await status_msg.edit_text("🚀 Submitting video to ApyHub compression queue...")

    # Step 1: Submit job (Default 50% compression strength)
    job_id = await submit_compress_job(path, compression_percentage=50)
    
    # Clean up local file
    if os.path.exists(path):
        os.remove(path)

    if not job_id:
        return await status_msg.edit_text("❌ Failed to submit compression job. Check your API token or file format.")

    await status_msg.edit_text(f"⏳ Compression job enqueued (`{job_id}`). Processing in background...")

    # Step 2: Poll for completion (up to 40 attempts, 3 seconds apart)
    max_attempts = 40
    output_url = None

    for attempt in range(1, max_attempts + 1):
        await asyncio.sleep(3.0)  # Safe polling interval
        
        job_data = await check_compress_job_status(job_id)
        status = job_data.get("status", "pending")

        if status == "successful":
            output_url = job_data.get("url")
            break
        elif status == "failed":
            error_msg = job_data.get("message", "Worker error")
            return await status_msg.edit_text(f"❌ Video compression failed: `{error_msg}`", parse_mode=ParseMode.MARKDOWN)
        
        if attempt % 5 == 0:
            await status_msg.edit_text(f"⏳ Compressing video... (Attempt {attempt}/{max_attempts})")

    if not output_url:
        return await status_msg.edit_text("⏱️ Job timed out while waiting for compression to complete.")

    await status_msg.edit_text("⬇️ Downloading compressed video result...")

    # Step 3: Download compressed file bytes and send back to Telegram
    async with httpx.AsyncClient(follow_redirects=True) as http_client:
        try:
            vid_resp = await http_client.get(output_url, timeout=60.0)
            if vid_resp.status_code != 200:
                return await status_msg.edit_text(f"🔗 **Video Compressed Successfully!**\n\nDownload Link: {output_url}")

            file_io = io.BytesIO(vid_resp.content)
            file_io.name = "compressed_video.mp4"

            await message.reply_video(
                video=file_io,
                caption="🎉 **Video Compressed Successfully!**\n_Powered by ApyHub Async Video Compressor_",
                parse_mode=ParseMode.MARKDOWN
            )
            await status_msg.delete()

        except Exception as e:
            await status_msg.edit_text(f"🔗 **Video Compressed Successfully!**\n\nDownload Link: {output_url}")


@app.on_message(filters.command("compresshelp"))
async def cmd_compress_help(client: Client, message: Message):
    """Command: /compresshelp"""
    help_text = (
        "📖 **ApyHub Video Compressor Bot — Guide**\n\n"
        "• Reply to any video file with `/compressvideo` to reduce its file size asynchronously.\n\n"
        "_Utilizes ApyHub's job enqueue and polling system._"
    )
    await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
