# Kane141

This project is for educational purposes only, do not use it against any law or to harm anyone, I am not responsible for any misuse of this project.

<img src="https://i.imgur.com/mGkRVa2.jpg">

<h1 align="center">Kane141</h1>

Kane141 is a free and open source game center for Linux, forked from [UnderTaker141](https://github.com/AbdelrhmanNile/UnderTaker141). It fetches all the repacks uploaded by [johncena141](https://1337x.to/user/johncena141/) on 1337x, then fetches their summary and cover art from [IGDB](igdb.com) and displays them in a "nice" UI :3.

Browse games with a paginated grid, and copy a game's magnet link straight from the app — bring your own torrent client to download it.

# IMPORTANT
- Please read [johncena141's guide](https://gitlab.com/jc141x/setup/-/tree/main) to understand more about how their repacks work, and double check the dependencies for their repacks.

# Dependencies
- Python 3.11+
- A torrent client of your choice (Kane141 no longer bundles one)
- All the dependencies for johncena141's repacks (check their [guide](https://gitlab.com/jc141x/setup/-/blob/main/README.md))

# Installation (from source)
```
git clone https://github.com/MustafaSofi/Kane141.git
cd Kane141
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd src
python3 app.py
```

# Configuration
After you run the app, head to the settings tab.

## IGDB
- Create a Twitch API app and get a client ID and secret from [here](https://dev.twitch.tv/console/apps/create)

# Updating the database
To update the database and fetch new releases by johncena141, head to the settings tab and click on the "Update database" button. This will take a few minutes and will freeze the app, just wait until it finishes and everything will return to normal.

# Downloading a game
Click a game to open its details, then click "Copy Magnet Link" to copy the magnet URI to your clipboard. Paste it into your torrent client of choice to start the download.
