import aiohttp
import random
import re

# GraphQL Query to fetch Anime
ANILIST_QUERY = """
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    media(type: ANIME, sort: POPULARITY_DESC) {
      id
      title { romaji english }
      description(asHtml: false)
      episodes
      genres
      averageScore
      coverImage { extraLarge }
      siteUrl
    }
  }
}
"""

async def fetch_random_anime() -> dict:
    """Fetches a random popular anime from AniList."""
    url = "https://graphql.anilist.co"
    # Pick a random page from the top ~2000 most popular anime
    variables = {"page": random.randint(1, 200), "perPage": 1}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={"query": ANILIST_QUERY, "variables": variables}) as resp:
            data = await resp.json()
            anime = data["data"]["Page"]["media"][0]
            
            # Clean up the description (AniList sometimes sends HTML tags in plain text)
            raw_desc = anime.get("description") or "No description available."
            clean_desc = re.sub(r"<[^>]+>", "", raw_desc)[:500] + "..."
            
            title = anime["title"].get("english") or anime["title"].get("romaji")
            genres = ", ".join(anime.get("genres", []))
            
            return {
                "title": title,
                "description": clean_desc,
                "episodes": anime.get("episodes", "?"),
                "genres": genres,
                "score": anime.get("averageScore", "?"),
                "image": anime["coverImage"]["extraLarge"],
                "url": anime["siteUrl"]
            }
