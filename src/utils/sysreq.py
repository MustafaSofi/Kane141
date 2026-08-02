"""
Look up a game's PC system requirements on Steam, on demand.
"""

import re
import requests

STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
STEAM_DETAILS_URL = "https://store.steampowered.com/api/appdetails"


def _strip_html(text):
    """Turn Steam's requirement HTML blob into readable plain text."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<li>", "\n- ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    return text.strip()


def get_system_requirements(game_name, timeout=8):
    """
    Search Steam for a game by name and return its PC system requirements
    as a formatted string, or None if nothing could be found.
    """
    try:
        search = requests.get(
            STEAM_SEARCH_URL,
            params={"term": game_name, "cc": "us", "l": "en"},
            timeout=timeout,
        )
        results = search.json().get("items", [])
        if not results:
            return None

        appid = results[0]["id"]

        details = requests.get(
            STEAM_DETAILS_URL,
            params={"appids": appid},
            timeout=timeout,
        )
        data = details.json().get(str(appid), {})
        if not data.get("success"):
            return None

        reqs = data["data"].get("pc_requirements")
        if not reqs or isinstance(reqs, list):  # empty list means no data
            return None

        minimum = reqs.get("minimum")
        if not minimum:
            return None

        return _strip_html(minimum)
    except Exception:
        return None
