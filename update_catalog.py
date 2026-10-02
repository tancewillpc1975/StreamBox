#!/usr/bin/env python3
import getpass, json, os, re, time, urllib.parse, urllib.request, urllib.error

API = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w500"
BACK = "https://image.tmdb.org/t/p/w1280"

# GitHub Actions supplies TMDB_API_KEY as a repository secret.
# When running manually, the script securely prompts for the key instead.
KEY = os.environ.get("TMDB_API_KEY", "").strip()
if KEY:
    KEY = ''.join(ch for ch in KEY if ch.isascii() and ch.isalnum())
    if not re.fullmatch(r"[0-9a-fA-F]{32}", KEY):
        raise SystemExit("TMDB_API_KEY is not a valid 32-character TMDB v3 API key.")
else:
    while True:
        KEY = getpass.getpass("Enter your TMDB v3 API key (32 characters): ").strip()
        KEY = ''.join(ch for ch in KEY if ch.isascii() and ch.isalnum())
        if re.fullmatch(r"[0-9a-fA-F]{32}", KEY):
            break
        print("That does not look like a TMDB v3 API key. Please paste the 32-character API Key (v3 auth), not the longer Read Access Token.")

def request_json(path, max_attempts=5):
    sep = "&" if "?" in path else "?"
    url = API + path + sep + urllib.parse.urlencode({"api_key": KEY})
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "StreamBox-Catalog-Updater/1.1"})

    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 401:
                raise SystemExit("TMDB rejected this key (401 Unauthorized). In TMDB Settings > API, copy the 32-character 'API Key (v3 auth)' and run the script again.\nTMDB response: " + body)
            if e.code in (429, 500, 502, 503, 504) and attempt < max_attempts:
                wait = min(2 ** attempt, 20)
                print(f"Temporary TMDB HTTP {e.code}. Retrying in {wait}s ({attempt}/{max_attempts})...")
                time.sleep(wait)
                continue
            raise SystemExit(f"TMDB request failed with HTTP {e.code}: {body}")
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as e:
            if attempt < max_attempts:
                wait = min(2 ** attempt, 20)
                print(f"Temporary network error: {e}. Retrying in {wait}s ({attempt}/{max_attempts})...")
                time.sleep(wait)
                continue
            raise SystemExit(f"TMDB request failed after {max_attempts} attempts: {e}")


def fetch(path, media):
    d = request_json(path)
    out = []
    for m in d.get("results", []):
        out.append({
            "id": m.get("id"),
            "media_type": media,
            "title": m.get("title") or m.get("name") or "Untitled",
            "poster": IMG + m["poster_path"] if m.get("poster_path") else None,
            "backdrop": BACK + m["backdrop_path"] if m.get("backdrop_path") else None,
            "rating": m.get("vote_average", 0),
            "overview": m.get("overview", "") or "",
            "release_date": m.get("release_date") or m.get("first_air_date") or "",
            "stream_url": None,
        })
    return out

print("Checking TMDB key...")
request_json("/configuration")
print("TMDB key accepted. Fetching catalog...")

catalog = {
    "updated_at": time.strftime("%Y-%m-%d %H:%M"),
    "movies": {
        "trending": fetch("/trending/movie/week", "movie"),
        "popular": fetch("/movie/popular", "movie"),
        "now_playing": fetch("/movie/now_playing", "movie"),
        "top_rated": fetch("/movie/top_rated", "movie"),
    },
    "series": {
        "trending": fetch("/trending/tv/week", "tv"),
        "popular": fetch("/tv/popular", "tv"),
        "airing_today": fetch("/tv/airing_today", "tv"),
        "top_rated": fetch("/tv/top_rated", "tv"),
    },
}

temp_catalog = "catalog.json.tmp"
with open(temp_catalog, "w", encoding="utf-8") as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)
    f.flush()
    os.fsync(f.fileno())

os.replace(temp_catalog, "catalog.json")

movie_count = sum(len(v) for v in catalog["movies"].values())
series_count = sum(len(v) for v in catalog["series"].values())
print(f"catalog.json updated: {movie_count} movie entries, {series_count} series entries")
