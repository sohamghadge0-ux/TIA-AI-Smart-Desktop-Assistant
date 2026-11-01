# ╔══════════════════════════════════════════════════════════════════╗
# ║  TIA AI — YOUTUBE & MEDIA                                       ║
# ║  Handles: YouTube direct play (scrapes videoId, not search      ║
# ║  results page), Spotify controls, open URL                      ║
# ║  Copyright (c) 2025 Soham Ghadge                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio, os, re, time, webbrowser, subprocess
import pyautogui, pyperclip, requests
from livekit.agents import function_tool

_YT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def _yt_urls(query: str, count: int = 5) -> list:
    """Scrape YouTube videoIds from search HTML — no API key needed."""
    try:
        r = requests.get(
            f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}",
            headers=_YT_HEADERS, timeout=10)
        ids = list(dict.fromkeys(re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', r.text)))
        return [f"https://www.youtube.com/watch?v={i}" for i in ids[:count]]
    except: return []

@function_tool()
async def play_media(query: str, platform: str = "youtube") -> str:
    """Play first YouTube video for query."""
    def _do():
        urls = _yt_urls(query, 1)
        if urls:
            webbrowser.open(urls[0]); time.sleep(3)
            pyautogui.press("k")  # YouTube play shortcut
            return f"✅ Playing '{query}'"
        webbrowser.open(f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}")
        return f"✅ YouTube search opened for '{query}'"
    return await asyncio.to_thread(_do)

@function_tool()
async def youtube_play_nth_result(query: str, n: int = 1) -> str:
    """Play Nth YouTube search result."""
    def _do():
        urls = _yt_urls(query, n+1)
        if urls and len(urls) >= n:
            webbrowser.open(urls[n-1]); time.sleep(3); pyautogui.press("k")
            return f"✅ Playing result #{n} for '{query}'"
        webbrowser.open(f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}")
        return f"✅ YouTube search opened"
    return await asyncio.to_thread(_do)

def _spotify():
    try: subprocess.Popen("spotify", shell=True)
    except: subprocess.Popen("start spotify:", shell=True)
    time.sleep(3)

@function_tool()
async def open_spotify() -> str:
    """Open Spotify app."""
    await asyncio.to_thread(_spotify); return "✅ Spotify opened"

@function_tool()
async def spotify_search_play_quick(song: str) -> str:
    """Search and play song on Spotify."""
    def _do():
        _spotify()
        pyautogui.hotkey("ctrl","k"); time.sleep(1)
        pyperclip.copy(song); pyautogui.hotkey("ctrl","v")
        time.sleep(1.5); pyautogui.press("enter"); time.sleep(1); pyautogui.press("enter")
    await asyncio.to_thread(_do); return f"✅ Playing '{song}'"

@function_tool()
async def spotify_next() -> str:
    """Next track on Spotify."""
    await asyncio.to_thread(pyautogui.hotkey,"ctrl","right"); return "✅ Next"

@function_tool()
async def spotify_previous() -> str:
    """Previous track on Spotify."""
    await asyncio.to_thread(pyautogui.hotkey,"ctrl","left"); return "✅ Previous"

@function_tool()
async def spotify_pause() -> str:
    """Pause or resume Spotify."""
    await asyncio.to_thread(pyautogui.hotkey,"ctrl","p"); return "✅ Pause/Resume"

@function_tool()
async def open_url(url: str) -> str:
    """Open URL in browser."""
    if not url.startswith("http"): url = "https://" + url
    await asyncio.to_thread(webbrowser.open, url); return f"✅ Opened: {url}"