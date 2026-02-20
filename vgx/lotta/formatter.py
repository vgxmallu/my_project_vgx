import datetime
import urllib.parse
from bs4 import BeautifulSoup

def strip_html(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text()[:500] + ("..." if len(soup.get_text()) > 500 else "")

def generate_tags(title):
    # Very basic tag generation from title words
    words = title.split()
    tags = [f"#{w.lower()}" for w in words if len(w) > 4][:3]
    return " ".join(tags)

def format_message(template: str, entry: dict, chat_info: dict, feed_info: dict) -> str:
    now = datetime.datetime.now()
    
    title = entry.get("title", "No Title")
    link = entry.get("link", "")
    content = strip_html(entry.get("summary", ""))
    
    # Telegram Instant View requires a specific target template/rhash from Telegram. 
    # For demonstration, we construct a generic generic fallback or iv link.
    encoded_link = urllib.parse.quote(link)
    instant_view = f"https://t.me/iv?url={encoded_link}&rhash=YOUR_IV_HASH"

    mapping = {
        "{{title}}": title,
        "{{content}}": content,
        "{{link}}": link,
        "{{shortlink}}": link, # Placeholder: integrate a URL shortener API here if needed
        "{{instantview}}": instant_view,
        "{{iv}}": instant_view,
        "{{tags}}": generate_tags(title),
        "{{y}}": str(now.year),
        "{{m}}": str(now.month).zfill(2),
        "{{d}}": str(now.day).zfill(2),
        "{{t}}": now.strftime("%H:%M"),
        "{{channel_title}}": chat_info.get("title", "Channel"),
        "{{channel_type}}": chat_info.get("type", "Channel"),
        "{{feed_title}}": feed_info.get("title", "RSS Feed"),
    }

    formatted = template
    for key, val in mapping.items():
        formatted = formatted.replace(key, str(val))
    return formatted

