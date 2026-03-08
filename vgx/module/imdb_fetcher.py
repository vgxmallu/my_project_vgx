import asyncio
import random
from imdb import Cinemagoer

ia = Cinemagoer()

def _safe_list(movie, key, limit=3):
    """Safely extracts a list of objects (like Cast or Directors) to a string."""
    items = movie.get(key, [])
    if not items: return "N/A"
    return ", ".join([str(i) for i in items[:limit]])

def fetch_random_popular(template: str) -> dict:
    """Blocking function to get a random popular movie/tv show and format it."""
    # 1. Get Top 100 Popular Movies & TV Shows
    popular_movies = ia.get_popular100_movies()
    popular_tv = ia.get_popular100_tv()
    
    # 2. Pick a random item
    random_choice = random.choice(popular_movies + popular_tv)
    movie_id = random_choice.movieID
    
    # 3. Fetch Full Details for that specific ID
    movie = ia.get_movie(movie_id, info=['main', 'plot', 'vote details', 'box office'])
    
    # 4. Map ALL requested variables
    replacements = {
        "{{query}}": "Random Popular",
        "{{title}}": movie.get('title', 'N/A'),
        "{{votes}}": movie.get('votes', 'N/A'),
        "{{aka}}": _safe_list(movie, 'akas', 1),
        "{{seasons}}": str(movie.get('number of seasons', 'N/A')),
        "{{box_office}}": movie.get('box office', {}).get('Budget', 'N/A') if isinstance(movie.get('box office'), dict) else 'N/A',
        "{{localized_title}}": movie.get('localized title', 'N/A'),
        "{{kind}}": movie.get('kind', 'N/A').title(),
        "{{imdb_id}}": movie_id,
        "{{cast}}": _safe_list(movie, 'cast', 5),
        "{{runtime}}": _safe_list(movie, 'runtimes', 1) + " min",
        "{{countries}}": _safe_list(movie, 'countries'),
        "{{certificates}}": _safe_list(movie, 'certificates', 1),
        "{{languages}}": _safe_list(movie, 'languages'),
        "{{director}}": _safe_list(movie, 'director', 2),
        "{{writer}}": _safe_list(movie, 'writer', 2),
        "{{producer}}": _safe_list(movie, 'producer', 2),
        "{{composer}}": _safe_list(movie, 'composer', 2),
        "{{cinematographer}}": _safe_list(movie, 'cinematographer', 2),
        "{{music_team}}": _safe_list(movie, 'music department', 2),
        "{{distributors}}": _safe_list(movie, 'distributors', 2),
        "{{release_date}}": _safe_list(movie, 'release dates', 1),
        "{{year}}": movie.get('year', 'N/A'),
        "{{genres}}": _safe_list(movie, 'genres'),
        "{{poster}}": movie.get('full-size cover url', ''),
        "{{plot}}": movie.get('plot', ['N/A'])[0].split('::')[0],
        "{{rating}}": movie.get('rating', 'N/A'),
        "{{url}}": f"https://www.imdb.com/title/tt{movie_id}/"
    }

    # 5. Build Final Text
    final_text = template
    for key, val in replacements.items():
        final_text = final_text.replace(key, str(val))
        
    return {"text": final_text, "poster": replacements["{{poster}}"]}

async def get_random_imdb_post(template: str) -> dict:
    """Wraps the blocking scrape in an async thread to prevent freezing the bot."""
    return await asyncio.to_thread(fetch_random_popular, template)
