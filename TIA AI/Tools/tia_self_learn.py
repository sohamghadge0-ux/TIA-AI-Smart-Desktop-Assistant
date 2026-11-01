# ╔══════════════════════════════════════════════════════════════════╗
# ║  TIA AI — SELF-LEARNING SYSTEM                                  ║
# ║  Handles: Learn from user, recall memories, search & answer     ║
# ║  Storage: tia_memory.json in home directory                     ║
# ║  Copyright (c) 2025 Soham Ghadge                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio, json, os
from datetime import datetime
import requests
from livekit.agents import function_tool

_MEMORY_FILE = os.path.join(os.path.expanduser("~"), "tia_memory.json")

def _load():
    try:
        if os.path.exists(_MEMORY_FILE):
            with open(_MEMORY_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except: pass
    return {"facts":[],"preferences":{}}

def _save(data):
    with open(_MEMORY_FILE,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)

def get_memory_context() -> str:
    """Called by agent.py to inject memory into TIA's prompt at startup."""
    mem = _load()
    parts = []
    if mem.get("facts"):
        recent = mem["facts"][-10:]
        parts.append("Learned: " + "; ".join(f"{f['value']}" for f in recent))
    if mem.get("preferences"):
        prefs = list(mem["preferences"].items())[:5]
        parts.append("Prefs: " + "; ".join(f"{k}={v}" for k,v in prefs))
    return "\n".join(parts)

def _groq(prompt: str) -> str:
    key = os.getenv("GROQ_API_KEY","").strip()
    if not key: return "❌ GROQ_API_KEY missing"
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json={"model":"llama3-70b-8192","messages":[{"role":"user","content":prompt}],"max_tokens":500},
            timeout=12)
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e: return f"❌ {e}"

@function_tool()
async def learn_from_user(fact: str, category: str = "general") -> str:
    """Learn and store user info."""
    mem = _load()
    mem.setdefault("facts",[]).append({"key":category,"value":fact,"date":datetime.now().strftime("%Y-%m-%d")})
    mem["facts"] = mem["facts"][-200:]
    _save(mem); return f"✅ Learned: {fact}"

@function_tool()
async def recall_memory(query: str) -> str:
    """Recall learned memory by query."""
    def _do():
        mem = _load(); q = query.lower(); matches = []
        for f in mem.get("facts",[]):
            if q in f.get("value","").lower() or q in f.get("key","").lower():
                matches.append(f"• {f['value']}")
        for k,v in mem.get("preferences",{}).items():
            if q in k.lower() or q in str(v).lower():
                matches.append(f"• {k}: {v}")
        return "📝 Found:\n"+"\n".join(matches[:10]) if matches else f"❌ Nothing found for '{query}'"
    return await asyncio.to_thread(_do)

@function_tool()
async def search_and_answer(query: str) -> str:
    """Search internet and answer."""
    def _do():
        answer = _groq(f"Answer accurately and concisely:\n{query}")
        mem = _load()
        mem.setdefault("facts",[]).append({"key":"search","value":f"Q:{query[:80]} A:{answer[:150]}","date":datetime.now().strftime("%Y-%m-%d")})
        _save(mem); return answer
    return await asyncio.to_thread(_do)