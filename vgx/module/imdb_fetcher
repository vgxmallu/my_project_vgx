import asyncio
import random
from imdb import Cinemagoer

ia = Cinemagoer()

def _safe_list(movie, key, limit=3):
    items = movie.get(key, [])
    if not items: return "N/A"
    return ", ".join([str(i) for i in items[:limit]])

def fetch_random_popular(template: str) -> dict:
    """Safely fetches a random movie, with fallbacks if IMDb blocks the request."""
    
    # 1. Attempt to get Popular 100
    try:
        movies_list = ia.get_popular100_movies() or []
        tv_list = ia.get_popular100_tv() or []
    except Exception:
        movies_list, tv_list = [], []

    # 2. FALLBACK: If Popular fails (empty list), try Top 250 instead
    if not movies_list and not tv_list:
        try:
            movies_list = ia.get_top250_movies() or []
            tv_list = ia.get_top250_tv() or []
        except Exception:
            pass

    # Combine whatever we successfully grabbed
    combined_list = movies_list + tv_list
    
    # 3. FINAL SAFETY CHECK: If it's STILL empty, return a safe error
    if not combined_list:
        return {"error": "IMDb servers blocked the request or returned empty data.", "text": "", "poster": ""}

    # 4. Pick a random item safely
    random_choice = random.choice(combined_list)
    movie_id = random_choice.movieID
    
    # Fetch Full Details
    try:
        movie = ia.get_movie(movie_id, info=['main', 'plot', 'vote details', 'box office'])
    except Exception as e:
        return {"error": f"Failed to fetch movie details: {e}", "text": "", "poster": ""}
    
    # Map variables
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

    final_text = template
    for key, val in replacements.items():
        final_text = final_text.replace(key, str(val))
        
    return {"text": final_text, "poster": replacements["{{poster}}"], "error": None}

async def get_random_imdb_post(template: str) -> dict:
    return await asyncio.to_thread(fetch_random_popular, template)
