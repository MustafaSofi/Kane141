import requests
import json
from .thread_with_return import ThreadWithReturnValue
from .steam_metadata import get_cover_and_summary as steam_get_cover_and_summary, NO_COVER
import os
import numpy as np
import time
import unidecode

class ReleasesFeed:
    def __init__(self, db_object):
        
        self.db = db_object
        
        self.feed_json_url = "https://github.com/jc141x/releases-feed/releases/latest/download/releases.json"
        
    
    def pipeline(self):
        
        feed = self.get_latest_feed()
        feed = self.format_feed(feed)
        
        feed = self.parallelize_update_game_records(feed)
        
        self.update_database(feed)
    
    
    def get_latest_feed(self):
        r = requests.get(self.feed_json_url)
        if r.status_code != 200:
            raise RuntimeError(
                f"Could not fetch the releases feed (HTTP {r.status_code}). "
                f"jc141x's releases-feed may be temporarily down -- try again later."
            )
        try:
            return r.json()
        except json.JSONDecodeError:
            raise RuntimeError(
                "The releases feed did not return valid data. "
                "jc141x's releases-feed may be temporarily down -- try again later."
            )
    
    def format_feed(self, feed):
        
        formated_feed = []
        
        schema = {
            "name": "",
            "size": "",
            "magnet": "",
            "pltfrm": "",
            "cover": "",
            "summary": "",
        }
        
        for record in feed:
            formated_feed.append(schema.copy())
            formated_feed[-1]["name"] = record["name"]
            formated_feed[-1]["size"] = record["total_size"]
            formated_feed[-1]["magnet"] = record["magnet_link"]    
            
        return formated_feed
    
    def get_cover_and_summary(self, game):
        
        game_info = self.db._get_game_info(game)
        
        if (game_info is not None):
            if game_info.cover is not None:
                return game_info.cover, game_info.description
        
        time.sleep(0.5)

        return steam_get_cover_and_summary(unidecode.unidecode(game))

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
        
        return json_array
    
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
            if results[i] is not None:
                json_array.extend(results[i])
        
        return json_array

    def update_database(self, json_array):
        
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
        print("updating db done")
