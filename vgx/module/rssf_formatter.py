import datetime
import urllib.parse
from bs4 import BeautifulSoup

def extract_image_and_text(html_content: str):
    soup = BeautifulSoup(html_content, "html.parser")
    # Try to find an image
    img_tag = soup.find("img")
    image_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else None
    
    # Clean text limit to 600 chars
    clean_text = soup.get_text(separator="\n").strip()[:600]
    if len(clean_text) == 600:
        clean_text += "..."
        
    return image_url, clean_text

def format_post(template: str, entry: dict, chat_info: dict, feed_info: dict):
    now = datetime.datetime.now()
    title = entry.get("title", "No Title")
    link = entry.get("link", "")
    
    raw_summary = entry.get("summary", entry.get("description", ""))
    image_url, clean_content = extract_image_and_text(raw_summary)
    
    # Generic Instant View Link (Requires actual Telegram IV hash in production)
    encoded_link = urllib.parse.quote(link)
    iv_link = f"https://t.me/iv?url={encoded_link}&rhash=YOUR_IV_HASH"
    
    tags = " ".join([f"#{w.lower()}" for w in title.split() if len(w) > 4][:3])

    mapping = {
        "{{title}}": title,
        "{{content}}": clean_content,
        "{{link}}": link,
        "{{shortlink}}": link, # Requires URL shortener API for actual shortening
        "{{instantview}}": iv_link,
        "{{iv}}": iv_link,
        "{{tags}}": tags,
        "{{y}}": str(now.year),
        "{{m}}": str(now.month).zfill(2),
        "{{d}}": str(now.day).zfill(2),
        "{{t}}": now.strftime("%H:%M"),
        "{{channel_title}}": chat_info.title if chat_info else "Channel",
        "{{channel_type}}": chat_info.type.value if chat_info else "Channel",
        "{{channel_description}}": getattr(chat_info, 'description', ""),
        "{{feed_title}}": feed_info.get("title", "RSS Feed"),
        "{{feed_description}}": feed_info.get("description", ""),
        "{{feed_homepage}}": feed_info.get("link", "")
    }

    formatted = template
    for key, val in mapping.items():
        formatted = formatted.replace(key, str(val))
        
    return formatted, image_url
