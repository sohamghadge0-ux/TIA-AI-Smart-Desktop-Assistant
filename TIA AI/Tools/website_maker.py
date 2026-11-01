# ╔══════════════════════════════════════════════════════════════════╗
# ║  TIA AI — WEBSITE MAKER                                         ║
# ║  Handles: Single-file HTML5 website generation, opens instantly ║
# ║  Copyright (c) 2025 Soham Ghadge                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio, os, webbrowser
import requests
from livekit.agents import function_tool

def _groq(prompt, tokens=3000):
    key = os.getenv("GROQ_API_KEY","").strip()
    if not key: return "❌ GROQ_API_KEY missing"
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}],
                  "max_tokens":tokens,"temperature":0.6},
            timeout=25)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e: return f"❌ {e}"

def _clean_html(text):
    if "```html" in text: return text.split("```html")[1].split("```")[0].strip()
    if "```" in text: return text.split("```")[1].split("```")[0].strip()
    return text.strip()

@function_tool()
async def create_advanced_website(topic: str, style: str = "modern") -> str:
    """Generate HTML website and open."""
    def _do():
        html = _groq(
            f"Create professional single-file HTML5 website about: {topic}\n"
            f"Style: {style}. Inline CSS+JS, responsive, navbar, hero, footer.\nReturn ONLY HTML.")
        if html.startswith("❌"): return html
        html = _clean_html(html)
        path = os.path.join(os.path.expanduser("~"),"Desktop",f"{topic.replace(' ','_')}.html")
        with open(path,"w",encoding="utf-8") as f: f.write(html)
        webbrowser.open(f"file:///{path}")
        return f"✅ Website created: {path}"
    try: return await asyncio.to_thread(_do)
    except Exception as e: return f"❌ {e}"