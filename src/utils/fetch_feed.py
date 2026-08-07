import concurrent.futures
import json
import logging
import requests
import unidecode
from utils.steam_metadata import get_cover_and_summary as steam_get_cover_and_summary, _SHARED_SESSION

logger = logging.getLogger("ReleasesFeed")

class ReleasesFeed:
    def __init__(self, db_object):
        self.db = db_object
        self.feed_json_url = "https://github.com/jc141x/releases-feed/releases/latest/download/releases.json"

    def pipeline(self):
        feed = self.get_latest_feed()
        formatted_feed = self.format_feed(feed)
        enriched_feed = self.parallelize_update_game_records(formatted_feed)
        self.update_database(enriched_feed)

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
            formatted.append({
                "name": record.get("name", ""),
                "size": record.get("total_size", ""),
                "magnet": record.get("magnet_link", ""),
                "pltfrm": "wine" if "Wine" in record.get("magnet_link", "") else ("native" if "Native" in record.get("magnet_link", "") else "unknown"),
                "cover": "",
                "summary": ""
            })
        return formatted

    def _process_item(self, item):
        name = item["name"]
        clean_name = name.split("-", 1)[0] if "-" in name else name.split("[", 1)[0]
        clean_name = clean_name.replace("–", "-").replace("’", "'").strip()
        item["name"] = clean_name

        # Check existing database info cache first
        info = self.db._get_game_info(clean_name)
        if info and info.cover:
            item["cover"] = info.cover
            item["summary"] = info.description
        else:
            item["cover"], item["summary"] = steam_get_cover_and_summary(unidecode.unidecode(clean_name))
        return item

    def parallelize_update_game_records(self, json_array):
        # Bounded thread pool for concurrent metadata enrichment
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(self._process_item, json_array))
        return results

    def update_database(self, json_array):
        self.db.delete_all()
        filtered = [x for x in json_array if x.get("pltfrm") in ("wine", "native", "unknown")]
        self.db.add_games_batch(filtered)
        logger.info("Feed database update completed successfully.")
