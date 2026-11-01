# ╔══════════════════════════════════════════════════════════════════╗
# ║           TIA AI — INFORMATION TOOLS                            ║
# ║           File: Tools/information.py                            ║
# ║           Handles: Weather, news, time, web search,             ║
# ║           global info queries                                   ║
# ║           APIs: wttr.in (weather), RSS feeds (news),            ║
# ║                 Groq LLM (global info)                          ║
# ║           Copyright (c) 2025 Soham Ghadge                       ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio
import os
import webbrowser
from datetime import datetime

import requests
from livekit.agents import function_tool


# ──────────────────────────────────────────────────────────────────
#  INTERNAL: Groq LLM caller for info queries
# ──────────────────────────────────────────────────────────────────

def _groq(prompt: str, max_tokens: int = 600) -> str:
    """Call Groq LLM for global/historical info queries."""
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        return "❌ GROQ_API_KEY missing in .env"
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama3-70b-8192",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens
            },
            timeout=12
        )
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ Error: {e}"


# ──────────────────────────────────────────────────────────────────
#  WEATHER  (uses wttr.in — no API key needed)
# ──────────────────────────────────────────────────────────────────

@function_tool()
async def get_weather(city: str = "Mumbai") -> str:
    """Get current weather for city."""
    def _do():
        try:
            r = requests.get(
                f"https://wttr.in/{requests.utils.quote(city)}?format=3",
                timeout=5
            )
            return f"🌤 {r.text.strip()}"
        except Exception as e:
            return f"❌ Weather error: {e}"
    return await asyncio.to_thread(_do)


# ──────────────────────────────────────────────────────────────────
#  NEWS  (uses free RSS feeds — no API key needed)
# ──────────────────────────────────────────────────────────────────

# Available categories and their RSS feed URLs
_NEWS_FEEDS = {
    "india":     "https://feeds.feedburner.com/ndtvnews-top-stories",
    "world":     "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "tech":      "https://feeds.feedburner.com/TechCrunch",
    "sports":    "https://sports.ndtv.com/rss/all",
    "bollywood": "https://www.bollywoodhungama.com/rss/news.xml",
    "cricket":   "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
}


@function_tool()
async def get_top_news(category: str = "india") -> str:
    """Get latest news headlines."""
    def _do():
        try:
            import xml.etree.ElementTree as ET
            feed_url = _NEWS_FEEDS.get(category.lower(), _NEWS_FEEDS["india"])
            r = requests.get(feed_url, timeout=8)
            items = ET.fromstring(r.content).findall(".//item")[:5]
            headlines = [
                i.find("title").text
                for i in items
                if i.find("title") is not None
            ]
            return "📰 " + "\n".join(f"• {h}" for h in headlines)
        except Exception as e:
            return f"❌ News error: {e}"
    return await asyncio.to_thread(_do)


# ──────────────────────────────────────────────────────────────────
#  TIME & DATE  (local system time, no API needed)
# ──────────────────────────────────────────────────────────────────

@function_tool()
async def get_time_info(query: str = "full") -> str:
    """Get current time date day."""
    now = datetime.now()
    q = query.lower()

    if "time" in q:
        return f"🕐 {now.strftime('%I:%M %p')}"
    elif "date" in q:
        return f"📅 {now.strftime('%d %B %Y')}"
    elif "day" in q:
        return f"📆 {now.strftime('%A')}"
    elif "year" in q:
        return f"📅 {now.year}"
    else:
        # Full info by default
        return f"📅 {now.strftime('%A, %d %B %Y')} — {now.strftime('%I:%M %p')}"


# ──────────────────────────────────────────────────────────────────
#  WEB SEARCH  (opens browser with search results)
# ──────────────────────────────────────────────────────────────────

@function_tool()
async def search_web(query: str, engine: str = "google") -> str:
    """Search web and open browser."""
    urls = {
        "google":  f"https://www.google.com/search?q={requests.utils.quote(query)}",
        "youtube": f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}",
        "bing":    f"https://www.bing.com/search?q={requests.utils.quote(query)}",
    }
    url = urls.get(engine.lower(), urls["google"])
    await asyncio.to_thread(webbrowser.open, url)
    return f"✅ Searching '{query}' on {engine}"


# ──────────────────────────────────────────────────────────────────
#  GLOBAL INFO  (uses Groq for geography, economy, world facts)
# ──────────────────────────────────────────────────────────────────

@function_tool()
async def get_global_info(query: str) -> str:
    """Answer global geography economy queries."""
    return await asyncio.to_thread(
        _groq,
        f"Answer this global information query accurately and concisely:\n{query}"
    )
