import asyncio
from imdb import Cinemagoer

ia = Cinemagoer()

def fetch_and_format_sync(query: str, template: str) -> dict:
    """Synchronous IMDb fetcher. Returns a dict with text and poster URL."""
    movies = ia.search_movie(query)
    if not movies:
        return {"error": "Movie/Series not found."}
        
    movie = movies[0]
    ia.update(movie, info=['main', 'plot', 'vote details', 'box office'])
    
    # Safe extractor helper
    def get_list(key, limit=3):
        items = movie.get(key, [])
        if not items: return "N/A"
        return ", ".join([str(i) for i in items[:limit]])

    # Build the massive placeholder dictionary
    data = {
        "{{query}}": query,
        "{{title}}": movie.get('title', 'N/A'),
        "{{votes}}": movie.get('votes', 'N/A'),
        "{{aka}}": get_list('akas', 1),
        "{{seasons}}": str(movie.get('number of seasons', 'N/A')),
        "{{box_office}}": movie.get('box office', {}).get('Budget', 'N/A'),
        "{{localized_title}}": movie.get('localized title', 'N/A'),
        "{{kind}}": movie.get('kind', 'N/A').title(),
        "{{imdb_id}}": movie.movieID,
        "{{cast}}": get_list('cast', 5),
        "{{runtime}}": get_list('runtimes', 1) + " min",
        "{{countries}}": get_list('countries'),
        "{{certificates}}": get_list('certificates', 1),
        "{{languages}}": get_list('languages'),
        "{{director}}": get_list('director', 2),
        "{{writer}}": get_list('writer', 2),
        "{{producer}}": get_list('producer', 2),
        "{{composer}}": get_list('composer', 2),
        "{{cinematographer}}": get_list('cinematographer', 2),
        "{{music_team}}": get_list('music department', 2),
        "{{distributors}}": get_list('distributors', 2),
        "{{release_date}}": get_list('release dates', 1),
        "{{year}}": movie.get('year', 'N/A'),
        "{{genres}}": get_list('genres'),
        "{{poster}}": movie.get('full-size cover url', ''),
        "{{plot}}": movie.get('plot', ['N/A'])[0].split('::')[0],
        "{{rating}}": movie.get('rating', 'N/A'),
        "{{url}}": f"https://www.imdb.com/title/tt{movie.movieID}/"
    }

    # Format the template
    formatted_text = template
    for key, val in data.items():
        formatted_text = formatted_text.replace(key, str(val))
        
    return {"text": formatted_text, "poster": data["{{poster}}"], "error": None}

async def get_imdb_post(query: str, template: str) -> dict:
    """Wraps the blocking IMDb call in an asyncio thread."""
    return await asyncio.to_thread(fetch_and_format_sync, query, template)
