import os
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain GOFILE_API_TOKEN

# --- AUTHENTICATION HELPER ---
def get_api_token() -> str:
    """Retrieves and validates the strict API token from configuration."""
    token = getattr(Config, "GOFILE_API_TOKEN", None)
    return token


# --- GOFILE API HELPERS (API KEY AUTHENTICATED) ---

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


async def upload_file_to_gofile(file_path: str, folder_id: str = None) -> dict:
    """Uploads a local file strictly authenticated with your Gofile API token."""
    token = get_api_token()
    if not token:
        return {"error": "Missing GOFILE_API_TOKEN in config.py. API key authentication is required."}

    server = await get_gofile_upload_server()
    if not server:
        return {"error": "Failed to retrieve an active upload server."}

    upload_url = f"https://{server}.gofile.io/contents/uploadfile"
    data = {}
    if folder_id:
        data["folderId"] = folder_id.strip()

    headers = {
        "Authorization": f"Bearer {token}"
    }

    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                resp = await client.post(upload_url, data=data, files=files, headers=headers, timeout=60.0)
                resp.raise_for_status()
                res_data = resp.json()
                if res_data.get("status") == "ok":
                    return res_data.get("data")
                return {"error": res_data.get("status", "Unknown upload rejection")}
        except Exception as e:
            print(f"Gofile Upload Exception: {e}")
            return {"error": str(e)}


async def create_gofile_folder(parent_folder_id: str, folder_name: str) -> dict:
    """Creates a new subfolder strictly authenticated via Bearer token."""
    token = get_api_token()
    if not token:
        return {"error": "Missing GOFILE_API_TOKEN in config.py."}

    url = "https://api.gofile.io/contents/createFolder"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    payload = {
        "parentFolderId": parent_folder_id.strip(),
        "folderName": folder_name.strip()
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=15.0)
            data = resp.json()
            if data.get("status") == "ok":
                return data.get("data")
            return {"error": data.get("status", "Unknown API error")}
        except Exception as e:
            return {"error": str(e)}


async def get_gofile_direct_link(content_id: str) -> str:
    """Retrieves direct download link / metadata authenticated via API token."""
    token = get_api_token()
    url = f"https://api.gofile.io/contents/{content_id}"
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    item_data = data.get("data", {})
                    if "directLink" in item_data:
                        return item_data["directLink"]
                    elif "files" in item_data:
                        first_file = list(item_data["files"].values())[0]
                        return first_file.get("link") or first_file.get("directLink")
        except Exception as e:
            print(f"Gofile Content Fetch Error: {e}")
        return None


# --- COMMAND HANDLERS ---

@app.on_message(filters.command(["gocreatefolder", "createfolder"]))
async def cmd_create_folder(client: Client, message: Message):
    """Command: /gocreatefolder <parent_folder_id> <folder_name>"""
    args = message.command
    if len(args) < 3:
        return await message.reply_text(
            "⚠️ **Usage:** `/gocreatefolder <parent_folder_id> <folder_name>`\n\n"
            "_Requires GOFILE_API_TOKEN configured in config.py_",
            parse_mode=ParseMode.MARKDOWN
        )

    parent_id = args[1]
    folder_name = " ".join(args[2:])
    
    msg = await message.reply_text(f"📁 Creating folder `{folder_name}`...")
    result = await create_gofile_folder(parent_id, folder_name)

    if "error" in result:
        return await msg.edit_text(f"❌ Failed to create folder: `{result['error']}`", parse_mode=ParseMode.MARKDOWN)

    folder_id = result.get("id")
    share_code = result.get("code")
    
    response_text = (
        f"📂 **Directory Created Successfully!**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 **Name:** `{folder_name}`\n"
        f"📌 **Folder ID:** `{folder_id}`\n"
        f"🔗 **Share Code:** `{share_code}`\n\n"
        f"_To upload files into this folder:_\n"
        f"`/gofile {folder_id}` (reply to any file)"
    )
    await msg.edit_text(response_text, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["gofile", "upload"]) & (filters.document | filters.photo | filters.video | filters.audio | filters.reply))
async def cmd_upload_to_gofile(client: Client, message: Message):
    """Command: /gofile [optional_folder_id] - Uploads file using API key authentication."""
    target_msg = message.reply_to_message if message.reply_to_message else message
    
    media = (
        target_msg.document or 
        target_msg.photo or 
        target_msg.video or 
        target_msg.audio
    )

    if not media:
        return await message.reply_text("⚠️ **Usage:** Send or reply to any file with `/gofile` or `/gofile <folder_id>`.")

    args = message.command
    target_folder_id = args[1] if len(args) > 1 else None

    status_msg = await message.reply_text("⬆️ Downloading file and uploading via API key...")

    try:
        local_path = await client.download_media(target_msg)
        if not local_path or not os.path.exists(local_path):
            return await status_msg.edit_text("❌ Failed to download media from Telegram.")

        upload_result = await upload_file_to_gofile(local_path, folder_id=target_folder_id)
        
        if os.path.exists(local_path):
            os.remove(local_path)

        if "error" in upload_result or not upload_result:
            err = upload_result.get("error", "Unknown error") if isinstance(upload_result, dict) else "Upload failed"
            return await status_msg.edit_text(f"❌ Upload failed: `{err}`", parse_mode=ParseMode.MARKDOWN)

        download_page = upload_result.get("downloadPage")
        file_name = upload_result.get("name", "Unknown File")
        file_id = upload_result.get("fileId")
        parent_folder = upload_result.get("parentFolder")

        response_text = (
            f"📤 **API Authenticated Upload Successful!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📂 **File Name:** `{file_name}`\n"
            f"📁 **Folder ID:** `{parent_folder}`\n"
            f"🔗 **Download Page:** {download_page}\n"
            f"📌 **File ID:** `{file_id}`\n\n"
            f"_To download back to Telegram:_\n"
            f"`/godownload {download_page}`"
        )
        await status_msg.edit_text(response_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")


@app.on_message(filters.command(["godownload", "gofileget"]))
async def cmd_download_from_gofile(client: Client, message: Message):
    """Command: /godownload <gofile_url_or_code>"""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/godownload https://gofile.io/d/XXXXXX`")

    query_input = args[1].strip()
    content_id = query_input.split("/")[-1]
    if "c=" in query_input:
        content_id = query_input.split("c=")[-1].split("&")[0]

    status_msg = await message.reply_text("🔍 Resolving direct download link...")

    direct_url = await get_gofile_direct_link(content_id)
    if not direct_url:
        return await status_msg.edit_text(f"🔗 **Resource Found:**\n{query_input}\n\n*(Direct link requires API Key token configuration).*")

    await status_msg.edit_text("⬇️ Downloading file bytes...")

    async with httpx.AsyncClient(follow_redirects=True) as http_client:
        try:
            resp = await http_client.get(direct_url, timeout=60.0)
            if resp.status_code != 200:
                return await status_msg.edit_text("❌ Failed to download file bytes.")

            file_name = direct_url.split("/")[-1].split("?")[0] or "gofile_download"
            file_bytes = resp.content

            await status_msg.edit_text("⬆️ Sending file to Telegram...")
            await message.reply_document(
                document=file_bytes,
                file_name=file_name,
                caption=f"📥 **Downloaded via API Key:**\n`{file_name}`",
                parse_mode=ParseMode.MARKDOWN
            )
            await status_msg.delete()

        except Exception as e:
            await status_msg.edit_text(f"❌ Download error: {str(e)}")


@app.on_message(filters.command("gofilehelp"))
async def cmd_gofile_help(client: Client, message: Message):
    """Command: /gofilehelp"""
    help_text = (
        "📖 **Gofile API-Key Bot — Guide**\n\n"
        "• **Create Folder:** `/gocreatefolder <parent_id> <name>`\n"
        "• **Upload File:** Reply with `/gofile` or `/gofile <folder_id>`\n"
        "• **Download File:** `/godownload <gofile_link>`\n\n"
        "_Strictly authenticated using Bearer Token (API Key)_"
    )
    await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
