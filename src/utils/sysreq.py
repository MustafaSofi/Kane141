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


def get_system_requirements(game_name, appid=None, timeout=8):
    """
    Look up a game's PC system requirements on Steam. If `appid` is given
    (stored on the Game record, extracted from the repack title during
    scraping), look it up directly -- far more reliable than name search.
    Falls back to name search if no appid is available. Returns a
    formatted string, or None if nothing could be found.
    """
    try:
        if appid:
            details = requests.get(
                STEAM_DETAILS_URL,
                params={"appids": appid},
                timeout=timeout,
            )
            data = details.json().get(str(appid), {})
            if data.get("success"):
                reqs = data["data"].get("pc_requirements")
                if reqs and not isinstance(reqs, list):
                    minimum = reqs.get("minimum")
                    if minimum:
                        return _strip_html(minimum)
            # appid lookup didn't pan out -- fall through to name search

        search = requests.get(
            STEAM_SEARCH_URL,
            params={"term": game_name, "cc": "us", "l": "en"},
            timeout=timeout,
        )
        results = search.json().get("items", [])
        if not results:
            return None

        found_appid = results[0]["id"]

        details = requests.get(
            STEAM_DETAILS_URL,
            params={"appids": found_appid},
            timeout=timeout,
        )
        data = details.json().get(str(found_appid), {})
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
