import datetime
import urllib.parse
from bs4 import BeautifulSoup

def strip_html(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    # Limit content length for Telegram
    return soup.get_text()[:600] + ("..." if len(soup.get_text()) > 600 else "")

def generate_tags(title):
    words = [w.lower() for w in title.split() if len(w) > 4]
    return " ".join([f"#{w}" for w in words[:3]])

def format_message(template: str, entry: dict, chat_info: dict, feed_info: dict) -> str:
    now = datetime.datetime.now()
    
    title = entry.get("title", "No Title")
    link = entry.get("link", "")
    content = strip_html(entry.get("summary", entry.get("description", "")))
    
    # Generic Instant View redirect for demonstration
    encoded_link = urllib.parse.quote(link)
    instant_view = f"https://t.me/iv?url={encoded_link}&rhash=YOUR_HASH"

    mapping = {
        "{{title}}": title,
        "{{content}}": content,
        "{{link}}": link,
        "{{shortlink}}": link, # Requires API integration for true shortlinks
        "{{instantview}}": instant_view,
        "{{iv}}": instant_view,
        "{{tags}}": generate_tags(title),
        "{{y}}": str(now.year),
        "{{m}}": str(now.month).zfill(2),
        "{{d}}": str(now.day).zfill(2),
        "{{t}}": now.strftime("%H:%M"),
        "{{channel_title}}": chat_info.get("title", "Channel"),
        "{{channel_type}}": chat_info.get("type", "Channel"),
        "{{channel_description}}": chat_info.get("description", ""),
        "{{feed_title}}": feed_info.get("title", "RSS Feed"),
        "{{feed_description}}": feed_info.get("description", ""),
        "{{feed_homepage}}": feed_info.get("link", ""),
    }

    formatted_text = template
    for key, val in mapping.items():
        formatted_text = formatted_text.replace(key, str(val))
    return formatted_text
