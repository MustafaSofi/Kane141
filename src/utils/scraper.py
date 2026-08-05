import threading
import csv
import json
import requests
try:
    import cloudscraper
    _HAS_CLOUDSCRAPER = True
except ImportError:
    _HAS_CLOUDSCRAPER = False
from bs4 import BeautifulSoup
import numpy as np
import pandas as pd

from utils.steam_metadata import get_cover_and_summary as steam_get_cover_and_summary, NO_COVER
from .thread_with_return import ThreadWithReturnValue
import time
import os
import re

DEBUGGING = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# 1337x.to itself tends to be the most heavily bot-protected of the bunch.
# Its mirrors often aren't, or are protected less aggressively -- try them
# in order and use whichever one actually responds.
MIRRORS = [
    "https://1337x.to",
    "https://1337xx.to",
    "https://1377x.to",
    "https://1337x.pro",
    "https://x1337x.ws",
    "https://1337x.so",
]


class JohnCena141Scraper:
    """
    Scrapes every page of johncena141's uploader profile on 1337x (or one of
    its mirrors) directly. Unlike the jc141x releases-feed (which is capped
    at the latest 2000 releases), this walks the full upload history --
    much slower, but complete. Useful as a fallback when the feed is
    capped or unavailable.
    """
    def __init__(
        self,
        csv_name,
        db_object,
        page_limit=None
    ):
        self.start_page_num = 1
        self.csv_name = csv_name

        # 1337x sits behind Cloudflare's bot protection, which a plain
        # requests.Session (even with browser headers) usually can't get
        # past. cloudscraper solves the basic JS challenge automatically;
        # fall back to a plain session (with a browser UA) if it's missing.
        if _HAS_CLOUDSCRAPER:
            self.session = cloudscraper.create_scraper()
            self.session.headers.update(HEADERS)
        else:
            self.session = requests.Session()
            self.session.headers.update(HEADERS)

        # find a mirror that actually responds before doing anything else
        self.mirror_base = self._find_working_mirror()
        
        if page_limit is None:
            self.page_limit = self.get_num_pages()
        else:
            self.page_limit = page_limit
        
        self.db = db_object
        self.reset_lists()

    @staticmethod
    def _extract_torrent_links(soup, mirror_base):
        """
        Scan a page for links matching the /torrent/<id>/<name>/ URL
        pattern. Works regardless of what wrapper markup a given mirror's
        theme uses around the listing, since that pattern itself is
        consistent across 1337x and its clones. Deduped, since rows
        often have two anchors (icon + title) pointing at the same href.
        """
        links = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            parts = href.split("/")
            if len(parts) > 1 and parts[1] == "torrent":
                full_url = mirror_base + href
                if full_url not in links:
                    links.append(full_url)
        return links

    def _find_working_mirror(self):
        for mirror in MIRRORS:
            try:
                resp = self.session.get(
                    f"{mirror}/johncena141-torrents/1/", timeout=10
                )
                if resp.status_code != 200:
                    print(f"Mirror {mirror} returned HTTP {resp.status_code}, trying next...")
                    continue

                # a 200 status isn't enough -- some mirrors return a 200
                # "empty"/interstitial page with no real listing content
                # (e.g. behind a JS challenge cloudscraper didn't actually
                # solve). Confirm there's real torrent content before
                # committing to this mirror.
                soup = BeautifulSoup(resp.content, "lxml")
                if self._extract_torrent_links(soup, mirror):
                    print(f"Using 1337x mirror: {mirror}")
                    return mirror
                print(f"Mirror {mirror} returned 200 but no torrent listing was found "
                      f"(likely a challenge/interstitial page), trying next...")
            except Exception as e:
                print(f"Mirror {mirror} failed ({e}), trying next...")
        raise RuntimeError(
            "None of the known 1337x mirrors returned a real torrent listing -- "
            "they may all be blocking automated requests right now. Try again later."
        )

    def get_num_pages(self):
        """
        Best-effort: try to read the last-page number off the pagination
        UI. Different 1337x mirrors style this differently (or not at
        all), so if we can't find it, fall back to a high safety cap --
        the real stopping condition is an empty page in run(), not this
        number.
        """
        link = f"{self.mirror_base}/johncena141-torrents/1/"
        page = self.session.get(link, timeout=15)

        if page.status_code != 200:
            raise RuntimeError(
                f"1337x returned HTTP {page.status_code} for the uploader page. "
                f"It may be blocking automated requests -- try again later."
            )
        soup = BeautifulSoup(page.content, "lxml")

        last_page_element = soup.find("li", class_="last")
        if last_page_element is not None:
            href = last_page_element.find("a")
            if href is not None and href.get("href"):
                match = re.findall(r"/johncena141-torrents/([0-9]+)/", href["href"])
                if match:
                    return int(match[0])

        # couldn't find it -- fall back to a high cap; run() will stop
        # early on the first empty page regardless
        print(
            "Could not find a 'last page' marker on this mirror's layout -- "
            "will scrape until an empty page is hit instead."
        )
        return 9999

    
    def reset_lists(self):
        self.urllist = []
        self.filenamelist = []
        self.seederlist = []
        self.leecherlist = []
        self.sizelist = []
        self.datelist = []
        self.splitarr = []
        self.magnetlinks = []

    def task1(self):
        for url1 in self.splitarr[0]:
            self.scrape_individual(url1)

    def task2(self):
        for url2 in self.splitarr[1]:
            self.scrape_individual(url2)

    def task3(self):
        for url3 in self.splitarr[2]:
            self.scrape_individual(url3)

    def scrape_individual(self, url):
        try:
            source = self.session.get(url, timeout=15).text
            soup = BeautifulSoup(source, "lxml")

            leftside = []
            rightside = []

            for h1_tag in soup.find("h1"):
                self.filenamelist.append(h1_tag)

            for ul_tag in soup.find_all("ul", {"class": "list"}):
                for li_tag in ul_tag.find_all("li"):
                    leftside.extend(
                        strong_tag.text for strong_tag in li_tag.find_all("strong")
                    )
                    rightside.extend(span_tag.text for span_tag in li_tag.find_all("span"))

            combined = np.column_stack([leftside, rightside])

            for each_detail in combined:
                if "Seeders" in each_detail[0]:
                    self.seederlist.append(each_detail[1])
                if "Leechers" in each_detail[0]:
                    self.leecherlist.append(each_detail[1])
                if "Total size" in each_detail[0]:
                    self.sizelist.append(each_detail[1])
                if "Date uploaded" in each_detail[0]:
                    self.datelist.append(each_detail[1])
            self.magnetlinks.append(
                soup.find(string="Magnet Download").find_parent("a").get("href")
            )
        except Exception as e:
            # one bad/slow page shouldn't kill an hours-long scrape run
            print(f"Skipping {url}: {e}")

    def _finish(self):
        print("scrapping is done")
        self.clean()
        json_data = self.to_json()
        self.push_to_db(json_data)

        # delete csv
        os.remove(f"{self.csv_name}.csv")

    def run(self):
        print("scrapping for games")

        while True:
            if self.start_page_num == self.page_limit:
                self._finish()
                return
            else:
                page_resp = self.session.get(
                    f"{self.mirror_base}/johncena141-torrents/{self.start_page_num}/",
                    timeout=15,
                )
                if page_resp.status_code != 200:
                    raise RuntimeError(
                        f"1337x returned HTTP {page_resp.status_code} on page "
                        f"{self.start_page_num} -- it may be rate-limiting or "
                        f"blocking the scrape. Try again later."
                    )
                soup = BeautifulSoup(page_resp.content, "lxml")

                # scan the whole page for torrent links rather than relying
                # on a specific wrapper element (<tbody>, a certain div
                # class, etc) -- different mirrors theme this differently,
                # but the /torrent/<id>/<name>/ URL pattern itself is
                # consistent across 1337x and its clones
                self.urllist = self._extract_torrent_links(soup, self.mirror_base)

                if not self.urllist:
                    if self.start_page_num == 1:
                        # nothing found on page 1 at all -- that's a real
                        # layout mismatch, not "end of results"
                        raise RuntimeError(
                            "Could not find any torrent links on page 1 -- "
                            "this mirror's layout may not match what the "
                            "scraper expects, or the request was blocked."
                        )
                    # later pages with nothing found just means we've paged
                    # past the end of johncena141's uploads
                    print(f"No more results after page {self.start_page_num - 1} -- done.")
                    self._finish()
                    return

                # split array for parralel scraping
                self.splitarr = np.array_split(self.urllist, 3)

                t1 = threading.Thread(target=self.task1, name="t1")
                t2 = threading.Thread(target=self.task2, name="t2")
                t3 = threading.Thread(target=self.task3, name="t3")

                t1.start()
                t2.start()
                t3.start()

                t1.join()
                t2.join()
                t3.join()

                combined = np.column_stack(
                    [
                        self.filenamelist,
                        self.seederlist,
                        self.leecherlist,
                        self.sizelist,
                        self.datelist,
                        self.magnetlinks,
                    ]
                )
                df = pd.DataFrame(combined)

                df.to_csv(f"{self.csv_name}.csv", mode="a", index=False)
                self.start_page_num += 1
                self.reset_lists()

    def clean(self):
        print("cleaning dataset")
        df = pd.read_csv(f"{self.csv_name}.csv")
        df = df.loc[df["0"] != "0"]
        df = df.loc[df["3"] != "0"]
        df = df.loc[df["3"] != "1"]


        ### adding readable column names
        data = [
            {
                "no": "",
                "name": "",
                "seeders": "",
                "leechers": "",
                "size": "",
                "date": "",
                "magnet": "",
                "pltfrm": "",
                "cover": "",
                "summary": "",
            }
        ]
        df_data = pd.DataFrame(data)
        df_data.to_csv(f"{self.csv_name}.csv", mode="w", index=False)

        df.to_csv(f"{self.csv_name}.csv", mode="a", index=True)
        print("cleaning is done")

    def to_json(self):
        print("converting csv to json")
        data = []
        # Open a csv reader called DictReader
        with open(f"{self.csv_name}.csv", encoding="utf-8") as csvf:
            csvReader = csv.DictReader(csvf)
            for rows in csvReader:
                data.append(rows)

        # remove first 2 rows
        data = data[2:]
        
        #with open(f"{self.csv_name}.json", "w", encoding="utf-8") as jsonf:
        #    jsonf.write(json.dumps(data, indent=4))

        print("converting to json is done")

        ## update pltfrm and trim name and get cover art
        return self.parallelize_update_game_records(data)

    def get_cover_and_summary(self, game):
        
        game_info = self.db._get_game_info(game)
        
        if (game_info is not None):
            if game_info.cover is not None:
                return game_info.cover, game_info.description
        
        time.sleep(0.5)

        return steam_get_cover_and_summary(game)

    def update_game_records(self, json_array):
                
        num = len(json_array)
        
        # udate platform info
        for i in range(num):
            try:
                if "Wine" in json_array[i]["magnet"]:
                    json_array[i]["pltfrm"] = "wine"
                elif "Native" in json_array[i]["magnet"]:
                    json_array[i]["pltfrm"] = "native"
            except KeyError:
                continue

        # normalize game names and get cover art
        for i in range(num):
            try:
                if "-" in json_array[i]["name"]:
                    json_array[i]["name"] = json_array[i]["name"].split("-", 1)[0]
                else:
                    json_array[i]["name"] = json_array[i]["name"].split("[", 1)[0]

                
                if '\"' in json_array[i]["name"]:
                    continue
                
                #print(json_array[i]["no"])

                json_array[i]["cover"], json_array[i]["summary"] = self.get_cover_and_summary(
                    json_array[i]["name"].replace("–", "-").replace("’", "'")
                )
                time.sleep(1) 
            except KeyError:
                continue

        if DEBUGGING:
            # save json
            with open(f"{self.csv_name}.json", "w", encoding="utf-8") as jsonf:
                jsonf.write(json.dumps(json_array, indent=4))
        
        return json_array

    def push_to_db(self, json_array):
        
        self.db.delete_all()
        
        num = len(json_array)
        
        for i in range(num):
            try:
                if json_array[i]["pltfrm"] == "wine" or json_array[i]["pltfrm"] == "native":
                    self.db.add_game(
                        json_array[i]["name"],
                        json_array[i]["cover"],
                        json_array[i]["size"],
                        json_array[i]["magnet"],
                        json_array[i]["pltfrm"],
                        json_array[i]["summary"],
                    )
            except KeyError:
                continue
        print("pushing to db done")
        
        
    def parallelize_update_game_records(self, json_array):
        
        num = 10
        
        # split json array into 10 chunks
        chunks = np.array_split(json_array, num)
        
        # convert chunks to list
        chunks = [list(i) for i in chunks]
        
        results = [None] * num
        
        start = time.time()
        
        threads = []
        for i in range(num):
            threads.append(ThreadWithReturnValue(target=self.update_game_records, args=(chunks[i],)))
            threads[i].start()
            time.sleep(1)
            
        
        # join threads
        for i in range(num):
            results[i] = threads[i].join()
            
        end = time.time()
        print(f"parallelize_update_game_records took {end - start} seconds")
        # merge results
        json_array = []
        for i in range(num):
            json_array.extend(results[i])
        
        return json_array
