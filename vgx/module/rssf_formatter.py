import datetime
from bs4 import BeautifulSoup

def format_post(template: str, entry: dict) -> str:
    # Safely extract and clean text
    raw_summary = entry.get("summary", entry.get("description", ""))
    clean_content = BeautifulSoup(raw_summary, "html.parser").get_text()[:600]
    
    now = datetime.datetime.now()
    title = entry.get("title", "No Title")
    link = entry.get("link", "")
    
    # Generate tags
    tags = " ".join([f"#{w.lower()}" for w in title.split() if len(w) > 4][:3])

    mapping = {
        "{{title}}": title,
        "{{content}}": clean_content + ("..." if len(clean_content) == 600 else ""),
        "{{link}}": link,
        "{{tags}}": tags,
        "{{y}}": str(now.year),
        "{{m}}": str(now.month).zfill(2),
        "{{d}}": str(now.day).zfill(2),
        "{{t}}": now.strftime("%H:%M"),
        # Note: Add premium mappings here as needed
    }

    formatted = template
    for key, val in mapping.items():
        formatted = formatted.replace(key, str(val))
    return formatted
