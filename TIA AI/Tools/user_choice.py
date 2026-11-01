# ╔══════════════════════════════════════════════════════════════════╗
# ║  TIA AI — MEMORY & REMINDERS                                    ║
# ║  Handles: Remember/recall facts, preferences, async reminders   ║
# ║  Storage: tia_facts.json in home directory                      ║
# ║  Copyright (c) 2025 Soham Ghadge                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio, json, os
from datetime import datetime, timedelta
from livekit.agents import function_tool

_HOME       = os.path.expanduser("~")
_FACTS_FILE = os.path.join(_HOME, "tia_facts.json")
_PREFS_FILE = os.path.join(_HOME, "tia_user_preferences.json")

def _load(path): 
    try:
        if os.path.exists(path):
            with open(path,"r",encoding="utf-8") as f: return json.load(f)
    except: pass
    return {}

def _save(path, data):
    with open(path,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)

@function_tool()
async def remember_fact(key: str, value: str) -> str:
    """Remember a fact about user."""
    facts = _load(_FACTS_FILE)
    facts[key.lower().strip()] = {"value":value,"saved_at":datetime.now().strftime("%Y-%m-%d %H:%M")}
    _save(_FACTS_FILE, facts)
    return f"✅ Remembered: {key} = {value}"

@function_tool()
async def recall_fact(key: str) -> str:
    """Recall a remembered fact."""
    facts = _load(_FACTS_FILE)
    e = facts.get(key.lower().strip())
    if e: return f"📝 {key}: {e['value']} (saved {e['saved_at']})"
    matches = {k:v for k,v in facts.items() if key.lower() in k}
    if matches: return "📝 Related:\n" + "\n".join(f"• {k}: {v['value']}" for k,v in matches.items())
    return f"❌ No fact found for '{key}'"

@function_tool()
async def save_user_preferences(key: str, value: str) -> str:
    """Save user preference key value."""
    prefs = _load(_PREFS_FILE)
    prefs[key] = value; _save(_PREFS_FILE, prefs)
    return f"✅ Preference: {key} = {value}"

@function_tool()
async def set_reminder(text: str, minutes: int = 5) -> str:
    """Set a reminder with timer."""
    fire_at = datetime.now() + timedelta(minutes=minutes)
    async def _fire():
        await asyncio.sleep(minutes * 60)
        print(f"\n🔔 REMINDER: {text}\n")
    asyncio.create_task(_fire())
    return f"✅ Reminder set: '{text}' in {minutes} min (at {fire_at.strftime('%I:%M %p')})"