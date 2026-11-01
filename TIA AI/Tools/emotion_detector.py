# ╔══════════════════════════════════════════════════════════════════╗
# ║  TIA AI — EMOTION DETECTOR                                      ║
# ║  Handles: Detecting Boss emotion from speech text,              ║
# ║  setting TIA response mode to match Boss's mood                 ║
# ║  Copyright (c) 2025 Soham Ghadge                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio
from livekit.agents import function_tool

_emotion = {"emotion": "neutral", "confidence": 1.0}
_mode    = "normal"

@function_tool()
async def detect_user_emotion() -> str:
    """Detect user emotion."""
    return f"Emotion: {_emotion['emotion']} | Mode: {_mode}"

@function_tool()
async def analyze_voice_emotion(text: str) -> str:
    """Analyze voice emotion from text."""
    global _emotion, _mode
    t = text.lower()
    if any(w in t for w in ["sad","udaas","dukhi","cry","rona","bura","hurt"]):
        e, m = "sad", "empathetic"
    elif any(w in t for w in ["angry","gussa","frustrated","irritated","ugh"]):
        e, m = "frustrated", "calm"
    elif any(w in t for w in ["happy","khush","excited","amazing","great","awesome","love"]):
        e, m = "happy", "energetic"
    elif any(w in t for w in ["tired","thaka","sleepy","bored","bore"]):
        e, m = "tired", "calm"
    elif any(w in t for w in ["worried","anxious","scared","nervous","tension"]):
        e, m = "anxious", "empathetic"
    else:
        e, m = "neutral", "normal"
    _emotion = {"emotion": e, "confidence": 0.85}
    _mode    = m
    return f"✅ Detected: {e} → TIA mode: {m}"