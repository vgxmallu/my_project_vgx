import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
import asyncio

def clean_html(raw_html):
    """Strips HTML tags to get pure text content for Markdown."""
    if not raw_html: return ""
    return BeautifulSoup(raw_html, "html.parser").get_text()[:500] + "..."

def extract_image(entry):
    """Tries to find an image in the RSS entry media or HTML content."""
    if 'media_content' in entry and len(entry.media_content) > 0:
        return entry.media_content[0].get('url')
    if 'summary' in entry:
        soup = BeautifulSoup(entry.summary, 'html.parser')
        img = soup.find('img')
        if img: return img.get('src')
    return None

async def parse_and_format(feed_doc: dict, chat_info: dict) -> list:
    """Parses a feed URL and formats new entries based on the template."""
    # feedparser is synchronous, run it in a thread to prevent blocking
    feed_data = await asyncio.to_thread(feedparser.parse, feed_doc["url"])
    new_posts = []
    
    for entry in reversed(feed_data.entries[:10]): # Check latest 10
        guid = entry.get('id', entry.get('link'))
        if guid in feed_doc.get("posted_guids", []):
            continue # Skip if already posted
            
        now = datetime.now()
        tags = " ".join([f"#{t.term.replace(' ', '')}" for t in entry.get('tags', [])[:3]])
        content = entry.get('summary', '')
        if feed_doc.get("format") == "Markdown":
            content = clean_html(content)
            
        # --- Placeholder Replacement Engine ---
        text = feed_doc.get("template", "{{title}}\n{{link}}")
        replacements = {
            "{{title}}": entry.get('title', 'No Title'),
            "{{content}}": content,
            "{{link}}": entry.get('link', ''),
            "{{shortlink}}": entry.get('link', ''), # Requires a URL shortener API for actual shortlinks
            "{{instantview}}": f"https://t.me/iv?url={entry.get('link', '')}&rhash=YOUR_IV_HASH", 
            "{{iv}}": f"https://t.me/iv?url={entry.get('link', '')}&rhash=YOUR_IV_HASH",
            "{{tags}}": tags,
            "{{y}}": now.strftime("%Y"),
            "{{m}}": now.strftime("%m"),
            "{{d}}": now.strftime("%d"),
            "{{t}}": now.strftime("%H:%M"),
            "{{channel_title}}": chat_info.get("title", ""),
            "{{feed_title}}": feed_data.feed.get("title", "RSS Feed")
        }
        
        for placeholder, value in replacements.items():
            text = text.replace(placeholder, str(value))
            
        new_posts.append({
            "guid": guid,
            "text": text,
            "image": extract_image(entry) if feed_doc.get("send_images") else None
        })
        
    return new_posts
