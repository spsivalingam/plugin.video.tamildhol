# CLAUDE.md — plugin.video.tamildhol

## Project Overview
Kodi video addon for streaming Tamil serials and shows from tamildhol.se. Addon ID: `plugin.video.tamildhol`.

## Tech Stack
- **Python 3** (Kodi Python API v3.0.0)
- **Kodi modules**: `xbmc`, `xbmcgui`, `xbmcplugin`, `xbmcaddon`
- **BeautifulSoup 4** (bundled in `lib/bs4/`)
- **soupsieve** (bundled in `lib/soupsieve/`)

## Project Structure
```
├── addon.xml           # Kodi addon manifest (metadata, dependencies, assets)
├── default.py          # Entry point — routing, UI list building, playback
├── scraper.py          # TamilDholScraper class — HTTP fetching, HTML parsing, stream extraction
├── lib/                # Bundled Python dependencies (bs4, soupsieve)
├── resources/          # Addon assets (icon.png, fanart.jpg)
├── docker-compose.yml  # Docker Kodi environment (noVNC GUI)
└── Makefile            # Dev workflow commands
```

## Key Architecture
- **`default.py`** handles Kodi plugin routing via URL query params (`action`, `query`, `url`). Functions: `show_home`, `do_search_dialog`, `show_search_results`, `play_video`.
- **`scraper.py`** contains `TamilDholScraper` which scrapes tamildhol.se. It fetches pages, parses HTML with BeautifulSoup, follows iframe embeds, decodes packed JS, and extracts `.m3u8`/`.mp4` stream URLs.
- Playback uses Kodi's `setResolvedUrl` with HTTP header piping (`|User-Agent=...&Referer=...`) and falls back to `Player.play()`.

## Development Notes
- No external package manager — dependencies are vendored in `lib/`.
- `lib/` is added to `sys.path` at runtime by both `default.py` (`import_scraper()`) and `scraper.py`.
- SSL context is created with `ssl.create_default_context()` for HTTPS requests.
- The scraper uses `urllib.request` (no `requests` library).

## Dev Workflow (Docker)
Kodi runs in Docker with a browser-accessible GUI via noVNC. No local Kodi install needed.

```bash
make up        # Start Kodi → open http://localhost:8080 (Chorus2 Web UI)
make restart   # Restart container to reload code changes
make logs      # Tail addon logs (filtered)
make shell     # Open bash inside the container
make check     # Validate addon with kodi-addon-checker
make launch    # Trigger addon via JSON-RPC
make zip       # Package for distribution
make clean     # Remove all Docker data
```

## Common Tasks
- **Add a new content source**: Add methods to `TamilDholScraper` in `scraper.py`, add routing in `default.py`'s `main()`.
- **Fix broken playback**: Check `get_stream_url()`, `_extract_stream_from_html()`, and `_decode_packed_js()` in `scraper.py` — the target site changes frequently.
- **Update base URL**: Change `TamilDholScraper.BASE_URL` in `scraper.py`.
