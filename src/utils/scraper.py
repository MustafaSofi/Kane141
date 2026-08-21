import concurrent.futures
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

try:
    import cloudscraper
    _HAS_CLOUDSCRAPER = True
except ImportError:
    _HAS_CLOUDSCRAPER = False

from utils.steam_metadata import get_cover_and_summary as steam_get_cover_and_summary, NO_COVER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Scraper")

CONSECUTIVE_EMPTY_PAGES_TO_STOP = 3
MAX_RETRIES_PER_PAGE = 3


def parse_upload_date(raw):
    """
    1337x's "Date uploaded" field is inconsistent: relative for recent
    uploads ("5 hours ago", "Yesterday", "3 days ago") and absolute for
    older ones ("Aug. 5th '25", "Jan. 1st 2024"). Returns an ISO
    "YYYY-MM-DD" string for sorting, or None if it can't be parsed --
    unparseable dates sort last (oldest) in SQLite's DESC ordering
    rather than corrupting the sort.
    """
    if not raw:
        return None
    raw = raw.strip()
    lower = raw.lower()
    now = datetime.now()

    try:
        if "just now" in lower or "min" in lower or "hour" in lower:
            return now.strftime("%Y-%m-%d")
        if lower == "yesterday":
            return (now - timedelta(days=1)).strftime("%Y-%m-%d")

        m = re.match(r"(\d+)\s*day", lower)
        if m:
            return (now - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")

        m = re.match(r"(\d+)\s*week", lower)
        if m:
            return (now - timedelta(weeks=int(m.group(1)))).strftime("%Y-%m-%d")

        m = re.match(r"(\d+)\s*month", lower)
        if m:
            return (now - timedelta(days=int(m.group(1)) * 30)).strftime("%Y-%m-%d")

        # absolute dates like "Aug. 5th '25" or "Jan. 1st 2024"
        cleaned = raw.replace("st", "").replace("nd", "").replace("rd", "").replace("th", "")
        cleaned = cleaned.replace(".", "").replace("'", " ").strip()
        cleaned = " ".join(cleaned.split())

        for fmt in ("%b %d %y", "%b %d %Y", "%B %d %Y", "%B %d %y"):
            try:
                return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    except Exception:
        pass
    return None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MIRRORS = [
    "https://www.1337xx.to",
    "https://www.1337x.to",
    "https://1377x.to",
    "https://1337x.pro",
    "https://x1337x.ws",
    "https://1337x.so",
]

CHECKPOINT_FILE = os.path.expanduser("~/.config/kane141/scraper_checkpoint.json")

class JohnCena141Scraper:
    """
    Optimized high-concurrency 1337x scraper with bounded ThreadPoolExecutor,
    checkpointing, and batch database loading.
    """
    def __init__(
        self,
        csv_name,
        db_object,
        page_limit=None,
        max_workers=8
    ):
        self.start_page_num = 1
        self.csv_name = csv_name
        self.db = db_object
        self.max_workers = max_workers

        if _HAS_CLOUDSCRAPER:
            self.session = cloudscraper.create_scraper()
        else:
            self.session = requests.Session()

        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries, pool_connections=max_workers*2, pool_maxsize=max_workers*2)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(HEADERS)

        self.mirror_base = self._find_working_mirror()
        
        if page_limit is None:
            self.page_limit = self.get_num_pages()
        else:
            self.page_limit = page_limit

        self.load_checkpoint()

    def load_checkpoint(self):
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, "r") as f:
                    data = json.load(f)
                    self.start_page_num = data.get("last_page", 1)
                    logger.info(f"Resuming scrape from page {self.start_page_num}")
            except Exception as e:
                logger.warning(f"Failed to read checkpoint: {e}")

    def save_checkpoint(self, page_num):
        try:
            os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
            with open(CHECKPOINT_FILE, "w") as f:
                json.dump({"last_page": page_num}, f)
        except Exception as e:
            logger.warning(f"Failed to write checkpoint: {e}")

    @staticmethod
    def _extract_torrent_links(soup, mirror_base):
        links = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            parts = href.split("/")
            if len(parts) > 1 and parts[1] == "torrent":
                full_url = urljoin(mirror_base, href)
                if full_url not in links:
                    links.append(full_url)
        return links

    def _find_working_mirror(self):
        for mirror in MIRRORS:
            try:
                resp = self.session.get(f"{mirror}/user/johncena141/1/", timeout=10)
                if resp.status_code != 200:
                    continue
                
                parsed_url = urlparse(resp.url)
                actual_base = f"{parsed_url.scheme}://{parsed_url.netloc}"
                soup = BeautifulSoup(resp.content, "lxml")
                
                if self._extract_torrent_links(soup, actual_base):
                    logger.info(f"Using 1337x mirror: {actual_base}")
                    return actual_base
            except Exception as e:
                logger.debug(f"Mirror {mirror} failed: {e}")
        raise RuntimeError("None of the known 1337x mirrors returned a real torrent listing.")

    def get_num_pages(self):
        link = f"{self.mirror_base}/user/johncena141/1/"
        page = self.session.get(link, timeout=15)
        if page.status_code != 200:
            raise RuntimeError(f"1337x returned HTTP {page.status_code}")
        soup = BeautifulSoup(page.content, "lxml")
        last_page_element = soup.find("li", class_="last")
        if last_page_element is not None:
            href = last_page_element.find("a")
            if href and href.get("href"):
                match = re.findall(r"/user/johncena141/([0-9]+)/", href["href"])
                if match:
                    return int(match[0])
        return 9999

    def _scrape_single_torrent(self, url):
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.content, "lxml")
            
            title_tag = soup.find("h1")
            filename = title_tag.text.strip() if title_tag else ""

            seeders, leechers, size, date, magnet = "", "", "", "", ""
            
            for ul_tag in soup.find_all("ul", {"class": "list"}):
                for li_tag in ul_tag.find_all("li"):
                    strongs = [s.text.strip() for s in li_tag.find_all("strong")]
                    spans = [s.text.strip() for s in li_tag.find_all("span")]
                    for k, v in zip(strongs, spans):
                        if "Seeders" in k: seeders = v
                        elif "Leechers" in k: leechers = v
                        elif "Total size" in k: size = v
                        elif "Date uploaded" in k: date = v

            mag_node = soup.find(string="Magnet Download")
            if mag_node:
                magnet = mag_node.find_parent("a").get("href", "")

            return {
                "name": filename,
                "url": url,
                "seeders": seeders,
                "leechers": leechers,
                "size": size,
                "date": date,
                "date_sort": parse_upload_date(date),
                "magnet": magnet
            }
        except Exception as e:
            logger.debug(f"Error scraping {url}: {e}")
            return None

    def run(self):
        logger.info("Starting optimized scraper...")
        consecutive_empty_pages = 0
        all_records = []
        seen_urls = set()

        while True:
            if self.start_page_num >= self.page_limit:
                break

            page_url = f"{self.mirror_base}/user/johncena141/{self.start_page_num}/"
            page_resp = None
            
            for attempt in range(1, MAX_RETRIES_PER_PAGE + 1):
                try:
                    resp = self.session.get(page_url, timeout=15)
                    if resp.status_code == 200:
                        page_resp = resp
                        break
                except Exception:
                    pass
                time.sleep(0.5 * attempt)

            if not page_resp:
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= CONSECUTIVE_EMPTY_PAGES_TO_STOP:
                    break
                self.start_page_num += 1
                continue

            soup = BeautifulSoup(page_resp.content, "lxml")
            torrent_urls = self._extract_torrent_links(soup, self.mirror_base)

            if not torrent_urls:
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= CONSECUTIVE_EMPTY_PAGES_TO_STOP:
                    break
                self.start_page_num += 1
                continue

            new_urls = [url for url in torrent_urls if url not in seen_urls]
            
            if not new_urls:
                logger.info(f"Pagination limit reached at page {self.start_page_num}. Stopping scraper.")
                break
                
            seen_urls.update(new_urls)
            consecutive_empty_pages = 0

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                results = list(executor.map(self._scrape_single_torrent, new_urls))

            valid_results = [r for r in results if r and r["name"]]
            all_records.extend(valid_results)

            self.save_checkpoint(self.start_page_num)
            self.start_page_num += 1

        self.enrich_and_push(all_records)
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)

    def run_incremental(self):
        """
        Fast "check for new repacks" mode: walks 1337x pages from page 1
        (newest uploads first) the same way run() does, but compares each
        page's torrent listing links against what's already in the local
        DB *before* visiting any detail pages. As soon as a page turns up
        zero unknown links, we've caught up to already-scraped content --
        stop there instead of walking the entire archive. Only the
        genuinely new torrents get their detail pages fetched and Steam
        metadata looked up. Never wipes the existing database.
        """
        logger.info("Checking for new repacks...")
        known_urls = self.db.get_known_torrent_urls()
        page_num = 1
        new_records = []
        consecutive_empty_pages = 0

        while True:
            page_url = f"{self.mirror_base}/user/johncena141/{page_num}/"
            page_resp = None

            for attempt in range(1, MAX_RETRIES_PER_PAGE + 1):
                try:
                    resp = self.session.get(page_url, timeout=15)
                    if resp.status_code == 200:
                        page_resp = resp
                        break
                except Exception:
                    pass
                time.sleep(0.5 * attempt)

            if not page_resp:
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= CONSECUTIVE_EMPTY_PAGES_TO_STOP:
                    logger.info(f"Stopping: {consecutive_empty_pages} consecutive failed pages")
                    break
                page_num += 1
                continue

            soup = BeautifulSoup(page_resp.content, "lxml")
            torrent_urls = self._extract_torrent_links(soup, self.mirror_base)

            if not torrent_urls:
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= CONSECUTIVE_EMPTY_PAGES_TO_STOP:
                    logger.info(f"Stopping: {consecutive_empty_pages} consecutive empty pages")
                    break
                page_num += 1
                continue

            consecutive_empty_pages = 0
            new_urls = [u for u in torrent_urls if u not in known_urls]

            if not new_urls:
                # every torrent on this page is already in the DB -- since
                # uploads are listed newest-first, everything past this
                # point is already known too. No need to go any further.
                logger.info(f"Caught up to known repacks at page {page_num} -- stopping.")
                break

            logger.info(f"page {page_num}: {len(new_urls)} new repack(s)")

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                results = list(executor.map(self._scrape_single_torrent, new_urls))

            valid_results = [r for r in results if r and r["name"]]
            new_records.extend(valid_results)

            # a page with SOME known links mixed in among new ones means
            # we've reached the boundary -- next page will be all-known,
            # so this is as far as we need to go
            if len(new_urls) < len(torrent_urls):
                logger.info(f"Reached boundary of new content at page {page_num} -- stopping.")
                break

            page_num += 1

        if not new_records:
            logger.info("No new repacks found -- database is already up to date.")
            return 0

        self.enrich_and_push(new_records, wipe=False)
        return len(new_records)

    def enrich_and_push(self, records, wipe=True):
        logger.info("Enriching records with Steam metadata...")
        
        records_to_fetch = []
        enriched = []
        
        # Pass 1: Local DB Check (Safe on Main Thread)
        for rec in records:
            name = rec["name"]
            name_lower = name.lower()
            has_wine = "wine" in name_lower
            has_native = "native" in name_lower
            if has_wine and not has_native:
                rec["pltfrm"] = "wine"
            elif has_native and not has_wine:
                rec["pltfrm"] = "native"
            else:
                rec["pltfrm"] = "unknown"

            # every jc141 repack title embeds the real Steam AppID, e.g.
            # "(Appid=1030300)" -- extract it from the RAW title (before
            # any cleaning) and use it for a direct, reliable Steam lookup
            # instead of guessing from a name string
            appid_match = re.search(r"(?i)appid\s*=\s*(\d+)", name)
            rec["appid"] = appid_match.group(1) if appid_match else None

            # split on " - " (with surrounding spaces) rather than any
            # bare "-", so titles that themselves contain a hyphen
            # ("SJ-19 Learns To Love!", "Zero-Sum Heart", "Yooka-Replaylee")
            # don't get mangled down to a single fragment word
            if " - " in name:
                clean_name = name.split(" - ", 1)[0]
            elif "-" in name:
                clean_name = name.split("-", 1)[0]
            else:
                clean_name = name.split("[", 1)[0]
            clean_name = clean_name.replace("–", "-").replace("’", "'").strip()
            rec["clean_name"] = clean_name
            rec["release_name"] = name  # keep the original raw title -- this
            # is what actually distinguishes two same-named entries (e.g.
            # two "Cuphead" results with different sizes are usually
            # different versions/updates/DLC bundles; the cleaned display
            # name alone can't show that, the raw title usually can)
            rec["name"] = clean_name

            info = self.db._get_game_info(clean_name)
            if info and info.cover:
                rec["cover"] = info.cover
                rec["summary"] = info.description
                enriched.append(rec)
            else:
                records_to_fetch.append(rec)

        # Pass 2: Steam API Fetch (Threaded for Speed)
        def fetch_steam(rec):
            rec["cover"], rec["summary"] = steam_get_cover_and_summary(
                rec["clean_name"], appid=rec.get("appid"), session=self.session
            )
            return rec

        if records_to_fetch:
            logger.info(f"Fetching Steam metadata for {len(records_to_fetch)} missing games...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                fetched_records = list(executor.map(fetch_steam, records_to_fetch))
            enriched.extend(fetched_records)

        if wipe:
            self.db.delete_all()
        self.db.add_games_batch(enriched)
        logger.info("Database updated successfully.")
