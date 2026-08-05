"""
Look up a game's cover art and short description on Steam's public store
API. No API key or account needed -- unlike IGDB, which requires a Twitch
developer app (and Twitch now requires phone verification to create one).
"""

import requests

NO_COVER = "https://images.igdb.com/igdb/image/upload/t_cover_big_2x/nocover.png"

STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
STEAM_DETAILS_URL = "https://store.steampowered.com/api/appdetails"


def get_cover_and_summary(game_name, timeout=8):
    """
    Search Steam for a game by name and return (cover_url, summary).
    Falls back to (NO_COVER, "No summary available") if nothing is found
    or the request fails for any reason.
    """
    try:
        search = requests.get(
            STEAM_SEARCH_URL,
            params={"term": game_name, "cc": "us", "l": "en"},
            timeout=timeout,
        )
        results = search.json().get("items", [])
        if not results:
            return NO_COVER, "No summary available"

        appid = results[0]["id"]

        details = requests.get(
            STEAM_DETAILS_URL,
            params={"appids": appid},
            timeout=timeout,
        )
        data = details.json().get(str(appid), {})
        if not data.get("success"):
            return NO_COVER, "No summary available"

        game_data = data["data"]
        cover = game_data.get("header_image") or NO_COVER
        summary = game_data.get("short_description") or "No summary available"

        return cover, summary
    except Exception:
        return NO_COVER, "No summary available"
