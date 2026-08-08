import concurrent.futures
import json
import logging
import re
import requests
import unidecode
from utils.steam_metadata import get_cover_and_summary as steam_get_cover_and_summary, _SHARED_SESSION

logger = logging.getLogger("ReleasesFeed")

class ReleasesFeed:
    """
    Pulls jc141x's releases-feed (capped at their latest ~2000 releases)
    and adds any repacks not already in the local database. This is
    INCREMENTAL and NEVER wipes the existing database -- it's meant for
    "check what's new" on a regular basis. For a complete historical
    rebuild, use JohnCena141Scraper's Full Rescan instead.
    """
    def __init__(self, db_object):
        self.db = db_object
        self.feed_json_url = "https://github.com/jc141x/releases-feed/releases/latest/download/releases.json"

    def pipeline(self):
        feed = self.get_latest_feed()
        formatted_feed = self.format_feed(feed)

        new_items = self._filter_new(formatted_feed)
        if not new_items:
            logger.info("No new repacks found -- database is already up to date.")
            return 0

        logger.info(f"Found {len(new_items)} new repack(s), fetching Steam metadata...")
        enriched_feed = self.parallelize_update_game_records(new_items)
        self.update_database(enriched_feed)
        return len(new_items)

    def get_latest_feed(self):
        r = _SHARED_SESSION.get(self.feed_json_url, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"Could not fetch releases feed (HTTP {r.status_code}).")
        try:
            return r.json()
        except json.JSONDecodeError:
            raise RuntimeError("Releases feed returned invalid JSON.")

    def format_feed(self, feed):
        formatted = []
        for record in feed:
            name = record.get("name", "")
            name_lower = name.lower()
            has_wine = "wine" in name_lower
            has_native = "native" in name_lower
            if has_wine and not has_native:
                pltfrm = "wine"
            elif has_native and not has_wine:
                pltfrm = "native"
            else:
                pltfrm = "unknown"

            formatted.append({
                "name": name,
                "size": record.get("total_size", ""),
                "magnet": record.get("magnet_link", ""),
                "pltfrm": pltfrm,
                "cover": "",
                "summary": ""
            })
        return formatted

    def _filter_new(self, formatted_feed):
        """Only keep items whose magnet link isn't already in the local
        database, so 'Update database' adds new repacks instead of
        re-fetching Steam metadata for everything every single time."""
        existing_magnets = {g.magnet for g in self.db.get_games() if g.magnet}
        return [
            item for item in formatted_feed
            if not item.get("magnet") or item["magnet"] not in existing_magnets
        ]

    def _process_item(self, item):
        name = item["name"]

        # the real Steam AppID is embedded in the raw title, e.g.
        # "(Appid=1030300)" -- extract it before the name gets cleaned,
        # for a direct/reliable Steam lookup instead of guessing by name
        appid_match = re.search(r"(?i)appid\s*=\s*(\d+)", name)
        item["appid"] = appid_match.group(1) if appid_match else None

        # split on " - " (with surrounding spaces) rather than any bare
        # "-", so titles that themselves contain a hyphen ("SJ-19 Learns
        # To Love!", "Zero-Sum Heart") don't get mangled to a fragment
        if " - " in name:
            clean_name = name.split(" - ", 1)[0]
        elif "-" in name:
            clean_name = name.split("-", 1)[0]
        else:
            clean_name = name.split("[", 1)[0]
        clean_name = clean_name.replace("–", "-").replace("’", "'").strip()
        item["name"] = clean_name

        # Check existing database info cache first
        info = self.db._get_game_info(clean_name)
        if info and info.cover:
            item["cover"] = info.cover
            item["summary"] = info.description
        else:
            item["cover"], item["summary"] = steam_get_cover_and_summary(
                unidecode.unidecode(clean_name), appid=item["appid"]
            )
        return item

    def parallelize_update_game_records(self, json_array):
        # Bounded thread pool for concurrent metadata enrichment
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(self._process_item, json_array))
        return results

    def update_database(self, json_array):
        # NOTE: no delete_all() here -- this only ADDS new repacks on top
        # of whatever's already in the database. Full Rescan (scraper.py)
        # is the one that does a full wipe + rebuild.
        filtered = [x for x in json_array if x.get("pltfrm") in ("wine", "native", "unknown")]
        self.db.add_games_batch(filtered)
        logger.info(f"Added {len(filtered)} new repack(s) to the database.")
