"""
Look up a game's cover art and short description on Steam's public store API.
Includes caching and exponential backoff rate-limiting.
"""

import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

NO_COVER = "https://images.igdb.com/igdb/image/upload/t_cover_big_2x/nocover.png"

STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
STEAM_DETAILS_URL = "https://store.steampowered.com/api/appdetails"

_CACHE = {}

def get_shared_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

_SHARED_SESSION = get_shared_session()

def get_cover_and_summary(game_name, timeout=8, session=None):
    """
    Search Steam for a game by name and return (cover_url, summary).
    Uses in-memory cache to skip redundant requests.
    """
    key = game_name.strip().lower()
    if key in _CACHE:
        return _CACHE[key]

    sess = session or _SHARED_SESSION

    try:
        search = sess.get(
            STEAM_SEARCH_URL,
            params={"term": game_name, "cc": "us", "l": "en"},
            timeout=timeout,
        )
        if search.status_code == 429:
            time.sleep(2)
            return NO_COVER, "No summary available"

        data_json = search.json()
        results = data_json.get("items", []) if isinstance(data_json, dict) else []
        if not results:
            _CACHE[key] = (NO_COVER, "No summary available")
            return _CACHE[key]

        appid = results[0]["id"]

        details = sess.get(
            STEAM_DETAILS_URL,
            params={"appids": appid},
            timeout=timeout,
        )
        if details.status_code == 429:
            time.sleep(2)
            return NO_COVER, "No summary available"

        data = details.json().get(str(appid), {})
        if not data.get("success"):
            _CACHE[key] = (NO_COVER, "No summary available")
            return _CACHE[key]

        game_data = data["data"]
        cover = game_data.get("header_image") or NO_COVER
        summary = game_data.get("short_description") or "No summary available"

        res = (cover, summary)
        _CACHE[key] = res
        return res
    except Exception:
        return NO_COVER, "No summary available"
