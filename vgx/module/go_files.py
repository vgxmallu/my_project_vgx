import os
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from vgx import app

# --- GOFILE API HELPERS ---

async def get_gofile_upload_server() -> str:
    """Queries Gofile API to get the best available active upload server dynamically."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("https://api.gofile.io/servers", timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "ok":
                servers = data.get("data", {}).get("servers", [])
                if servers:
                    return servers[0].get("name")
        except Exception as e:
            print(f"Gofile Server Selection Error: {e}")
        return None


async def upload_file_to_gofile(file_path: str) -> dict:
    """Uploads a local file path to Gofile.io using multipart/form-data."""
    server = await get_gofile_upload_server()
    if not server:
        return None

    upload_url = f"https://{server}.gofile.io/contents/uploadfile"
    
    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                resp = await client.post(upload_url, files=files, timeout=60.0)
                resp.raise_for_status()
                res_data = resp.json()
                if res_data.get("status") == "ok":
                    return res_data.get("data")
        except Exception as e:
            print(f"Gofile Upload Exception: {e}")
        return None


async def get_gofile_direct_link(content_id: str) -> str:
    """Retrieves direct download link / metadata for a given Gofile content ID or share code."""
    url = f"https://api.gofile.io/contents/{content_id}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    item_data = data.get("data", {})
                    # If it's a file, return its primary download link
                    if "directLink" in item_data:
                        return item_data["directLink"]
                    elif "files" in item_data:
                        # Folder payload children extraction
                        first_file = list(item_data["files"].values())[0]
                        return first_file.get("link") or first_file.get("directLink")
        except Exception as e:
            print(f"Gofile Content Fetch Error: {e}")
        return None


# --- COMMAND HANDLERS ---

@app.on_message(filters.command(["gofile", "upload"]) & (filters.document | filters.photo | filters.video | filters.audio | filters.reply))
async def cmd_upload_to_gofile(client: Client, message: Message):
    """Command: /gofile or /upload - Sends a file/media to Gofile and returns shareable links."""
    target_msg = message.reply_to_message if message.reply_to_message else message
    
    media = (
        target_msg.document or 
        target_msg.photo or 
        target_msg.video or 
        target_msg.audio
    )

    if not media:
        return await message.reply_text("⚠️ **Usage:** Send or reply to any file, photo, video, or audio with `/gofile` to upload it.")

    status_msg = await message.reply_text("⬆️ Downloading file from Telegram & uploading to Gofile...")

    try:
        # Download file locally into temporary storage
        local_path = await client.download_media(target_msg)
        if not local_path or not os.path.exists(local_path):
            return await status_msg.edit_text("❌ Failed to download media from Telegram.")

        # Upload to Gofile API
        upload_result = await upload_file_to_gofile(local_path)
        
        # Clean up local file
        if os.path.exists(local_path):
            os.remove(local_path)

        if not upload_result:
            return await status_msg.edit_text("❌ Failed to upload file to Gofile storage servers.")

        download_page = upload_result.get("downloadPage")
        file_name = upload_result.get("name", "Unknown File")
        file_id = upload_result.get("fileId")

        response_text = (
            f"📤 **Gofile Upload Successful!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📂 **File Name:** `{file_name}`\n"
            f"🔗 **Download Page:** {download_page}\n"
            f"📌 **Content ID:** `{file_id}`\n\n"
            f"_To download this file back into Telegram later, use:_\n"
            f"`/godownload {download_page}`"
        )
        await status_msg.edit_text(response_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

    except Exception as e:
        await status_msg.edit_text(f"❌ Error during upload process: {str(e)}")


@app.on_message(filters.command(["godownload", "gofileget"]))
async def cmd_download_from_gofile(client: Client, message: Message):
    """Command: /godownload <gofile_url_or_code> - Downloads a file from Gofile and sends it to chat."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/godownload https://gofile.io/d/XXXXXX` or provide the 6/8-character code.")

    query_input = args[1].strip()
    
    # Extract code/contentId if full URL is passed
    content_id = query_input.split("/")[-1]
    if "c=" in query_input:
        content_id = query_input.split("c=")[-1].split("&")[0]

    status_msg = await message.reply_text("🔍 Resolving Gofile direct download link...")

    direct_url = await get_gofile_direct_link(content_id)
    if not direct_url:
        # Fallback to general download page info if direct link is restricted
        return await status_msg.edit_text(
            f"🔗 **Gofile Resource Found:**\n{query_input}\n\n"
            "*(Note: Direct binary downloading requires public or direct link permissions enabled on the file).*",
            disable_web_page_preview=True
        )

    await status_msg.edit_text("⬇️ Downloading file from Gofile server to bot...")

    async with httpx.AsyncClient(follow_redirects=True) as http_client:
        try:
            resp = await http_client.get(direct_url, timeout=60.0)
            if resp.status_code != 200:
                return await status_msg.edit_text("❌ Failed to download file bytes from Gofile storage.")

            file_name = direct_url.split("/")[-1].split("?")[0] or "gofile_download"
            file_bytes = resp.content

            await status_msg.edit_text("⬆️ Uploading file back to Telegram...")
            
            # Send file back to user based on size/type
            await message.reply_document(
                document=file_bytes,
                file_name=file_name,
                caption=f"📥 **Downloaded from Gofile:**\n`{file_name}`",
                parse_mode=ParseMode.MARKDOWN
            )
            await status_msg.delete()

        except Exception as e:
            await status_msg.edit_text(f"❌ Download error: {str(e)}")


@app.on_message(filters.command("gofilehelp"))
async def cmd_gofile_help(client: Client, message: Message):
    """Command: /gofilehelp - Displays command documentation."""
    help_text = (
        "📖 **Gofile.io Bot — Command Guide**\n\n"
        "• **Upload Any File:** Send or reply to any document, photo, video, or audio with `/gofile` or `/upload`.\n"
        "• **Download File:** `/godownload <gofile_link_or_code>` to pull files back into Telegram.\n"
        "• **Help Guide:** `/gofilehelp`\n\n"
        "_Powered by Gofile API — Unlimited size file sharing!_"
    )
    await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
