# Kane141

This project is for educational purposes only, do not use it against any law or to harm anyone, I am not responsible for any misuse of this project.

<img src="https://i.imgur.com/mGkRVa2.jpg">

<h1 align="center">Kane141</h1>

Kane141 is a free and open source game center for Linux, forked from [UnderTaker141](https://github.com/AbdelrhmanNile/UnderTaker141). It fetches repacks uploaded by [johncena141](https://1337x.to/user/johncena141/) on 1337x, then fetches their summary and cover art from Steam's public store API and displays them in a "nice" UI :3.

Browse games with a paginated grid, and copy a game's magnet link straight from the app — bring your own torrent client to download it.

# IMPORTANT
- Please read [johncena141's guide](https://gitlab.com/jc141x/setup/-/tree/main) to understand more about how their repacks work, and double check the dependencies for their repacks.

# What's different from UnderTaker141
- **No qBittorrent** — Kane141 doesn't manage downloads for you. Click a game, hit "Copy Magnet Link", and paste it into whatever torrent client you already use.
- **Paginated browsing** instead of a fixed random 50 games, with Prev/Next controls.
- **Steam-powered metadata** — cover art, descriptions, and minimum system requirements (shown when you click a game) all come from Steam's public store API. No account, API key, or signup required for any of it (previously required a Twitch developer app for IGDB, which now requires phone verification to create).
- **Game size shown on the card** itself, before you click in.
- **Two ways to populate the database**, from Settings:
  - **Update database** — fast, pulls from [jc141x's releases-feed](https://github.com/jc141x/releases-feed). Note: this feed is capped at the **2000 most recent** releases, and each update fully replaces your local database with whatever's currently in that feed (it doesn't merge/accumulate).
  - **Full Rescan (1337x, slow)** — walks johncena141's entire upload history directly, for older titles that have aged out of the capped feed. Can take hours. Tries several known 1337x mirrors and validates each one actually returns real content (not just an HTTP 200) before using it, since 1337x's mirrors are behind varying levels of Cloudflare protection and this can fail entirely if all of them are currently blocking or down — if so, it fails with a clear error rather than hanging or crashing.
- Renamed throughout, config lives at `~/.config/kane141/` instead of `~/.config/undertaker141/`.

# Dependencies
- Python 3.11–3.13 (Kivy doesn't reliably support 3.14+ yet as of this writing — you'll likely hit a window-provider crash)
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

Or from the repo root, use the included run script:
```
./run.sh
```

# Building an AppImage
```
chmod +x build/linux/buildAppImage.sh
./build/linux/buildAppImage.sh
```
This freezes the app with PyInstaller, assembles an AppDir, and packages it into `dist/Kane141-x86_64.AppImage` (downloading `appimagetool` automatically on first run if needed). Requires `Kane141.png` at the repo root for the icon.

# Configuration
No API keys or accounts needed — cover art, descriptions, and system requirements are all pulled from Steam's public store API.

# Updating the database
Head to the Settings tab:
- **Update database** — quick, pulls the latest 2000 releases from jc141x's feed. Takes a few minutes; the app will be unresponsive while it runs, just wait for it to finish.
- **Full Rescan (1337x, slow)** — use this if a specific title isn't showing up (it may have aged out of the capped feed). Scrapes johncena141's full upload history directly from 1337x/its mirrors. This depends entirely on 1337x's current anti-bot posture and can fail if every known mirror is blocking automated requests at the time — if that happens, the app will tell you clearly rather than hang.

Either way, don't close the app while an update is running.

# Downloading a game
Click a game to open its details. Minimum system requirements load automatically from Steam. Click "Copy Magnet Link" to copy the magnet URI to your clipboard, then paste it into your torrent client of choice to start the download.
