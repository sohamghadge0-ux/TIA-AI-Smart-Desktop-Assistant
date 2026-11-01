# ╔══════════════════════════════════════════════════════════════════╗
# ║  TIA AI — SCREEN ANALYZER                                       ║
# ║  Handles: Silent screen clicking, AI vision, code fixing        ║
# ║  Vision: GPT-4o → Gemini → Claude (Anthropic) fallback chain    ║
# ║  Copyright (c) 2025 Soham Ghadge                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio, os, base64, io, re, time, json, urllib.request, urllib.error
import pyautogui, pyperclip
from livekit.agents import function_tool


# ── Screenshot helper ─────────────────────────────────────────────
def _screenshot() -> bytes:
    from PIL import Image
    img = pyautogui.screenshot()
    w, h = img.size
    # FIX: was `w > 1280` — now also handles w == 1280 edge case properly
    if w >= 1280:
        new_w = 1280
        new_h = int(h * new_w / w)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ── Vision helper ─────────────────────────────────────────────────
def _vision(image_bytes: bytes, prompt: str) -> str:
    b64 = base64.b64encode(image_bytes).decode()

    def _openai_call(model: str) -> str | None:
        ok = os.getenv("OPENAI_API_KEY", "").strip()
        if not ok:
            return None
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}", "detail": "high"
                }}
            ]}],
            "max_tokens": 600
        }).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {ok}"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            print(f"⚠️ OpenAI {model} HTTP {e.code}: {e.read().decode(errors='ignore')[:200]}")
            return None
        except Exception as ex:
            print(f"⚠️ OpenAI {model} error: {ex}")
            return None

    def _gemini_call(model: str, api_ver: str = "v1beta") -> str | None:
        gk = os.getenv("GOOGLE_API_KEY", "").strip()
        if not gk:
            return None
        gp = json.dumps({
            "contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64}}
            ]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 600}
        }).encode()
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/{api_ver}/models/{model}:generateContent?key={gk}",
            data=gp,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                parts = json.loads(r.read())["candidates"][0]["content"]["parts"]
                if parts and "text" in parts[0]:
                    return parts[0]["text"].strip()
                return None
        except urllib.error.HTTPError as e:
            print(f"⚠️ Gemini {model} HTTP {e.code}: {e.read().decode(errors='ignore')[:200]}")
            return None
        except Exception as ex:
            print(f"⚠️ Gemini {model} error: {ex}")
            return None

    # ── Try all models in order ───────────────────────────────────
    for oai_model in ["gpt-4o", "gpt-4o-mini"]:
        r = _openai_call(oai_model)
        if r:
            return r

    for gm in ["gemini-2.0-flash-lite", "gemini-2.0-flash-lite-001",
               "gemini-2.0-flash-001", "gemini-2.0-flash"]:
        r = _gemini_call(gm, "v1beta")
        if r:
            return r

    # FIX: 1.5 models use v1beta too — v1 was causing HTTP 404 for all of them
    for gm in ["gemini-1.5-flash-latest", "gemini-1.5-pro-latest",
               "gemini-1.5-flash", "gemini-1.5-pro"]:
        r = _gemini_call(gm, "v1beta")
        if r:
            return r

    # FIX: Claude claude-haiku-4-5 as final fallback — fast, cheap, handles vision
    # Works automatically if ANTHROPIC_API_KEY is set in the environment
    ak = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if ak:
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 600,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/jpeg", "data": b64
                }},
                {"type": "text", "text": prompt}
            ]}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type": "application/json",
                     "x-api-key": ak,
                     "anthropic-version": "2023-06-01"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                for block in json.loads(r.read()).get("content", []):
                    if block.get("type") == "text":
                        return block["text"].strip()
        except urllib.error.HTTPError as e:
            print(f"⚠️ Claude claude-haiku-4-5 HTTP {e.code}: {e.read().decode(errors='ignore')[:200]}")
        except Exception as ex:
            print(f"⚠️ Claude claude-haiku-4-5 error: {ex}")

    # ── FREE LOCAL FALLBACK: Ollama (no API key, no billing, runs on-device) ──
    # Install once: https://ollama.com  then run: ollama pull llava
    # After that, vision works 100% offline forever at zero cost.
    for ollama_model in ["llava", "llava:13b", "moondream"]:
        try:
            payload = json.dumps({
                "model": ollama_model,
                "prompt": prompt,
                "images": [b64],
                "stream": False
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read()).get("response", "").strip()
                if result:
                    return result
        except urllib.error.URLError:
            # Ollama not running or not installed — silently skip
            break
        except Exception as ex:
            print(f"⚠️ Ollama {ollama_model} error: {ex}")

    missing = []
    if not os.getenv("OPENAI_API_KEY", "").strip():    missing.append("OPENAI_API_KEY")
    if not os.getenv("GOOGLE_API_KEY", "").strip():    missing.append("GOOGLE_API_KEY")
    if not os.getenv("ANTHROPIC_API_KEY", "").strip(): missing.append("ANTHROPIC_API_KEY")
    hint = (f" (missing: {', '.join(missing)})" if missing
            else " (all keys quota exhausted — add credits to OpenAI / Google / Anthropic)")
    return (f"❌ Vision unavailable{hint}\n"
            f"💡 Free fix: install Ollama from https://ollama.com then run: ollama pull llava")


# ── Smart Screen Action ───────────────────────────────────────────
@function_tool()
async def smart_screen_action(task: str) -> str:
    """See screen silently and click element."""
    try:
        img = await asyncio.to_thread(_screenshot)
        w, h = pyautogui.size()
        result = await asyncio.to_thread(
            _vision, img,
            f"Screen resolution: {w}x{h}. Task: {task}\n"
            f"Find the element and reply ONLY with x,y coordinates. Example: 640,380"
        )

        # FIX: Bail early if vision failed — don't try to parse error strings
        if not result or result.startswith("❌"):
            return f"❌ Vision failed: {result}"

        nums = re.findall(r"\d+", result.strip())
        if len(nums) >= 2:
            x, y = int(nums[0]), int(nums[1])
            if 0 < x < w and 0 < y < h:
                pyautogui.moveTo(x, y, duration=0.15)
                time.sleep(0.1)
                pyautogui.click(x, y)
                time.sleep(0.3)
                return f"✅ Done: {task}"
            return f"❌ Coordinates out of bounds: {x},{y} (screen is {w}x{h})"
        return f"❌ Could not find element for: {task} (vision said: {result[:100]})"
    except Exception as e:
        return f"❌ {e}"


# ── Analyze Screen ────────────────────────────────────────────────
@function_tool()
async def analyze_screen(query: str = "What is on screen?") -> str:
    """Analyze screen with AI vision."""
    try:
        img = await asyncio.to_thread(_screenshot)
        result = await asyncio.to_thread(
            _vision, img,
            f"Analyze this screenshot. Question: {query}\n"
            f"Describe what app is open and what is visible."
        )
        # FIX: Distinguish error from actual analysis result
        if not result:
            return "❌ Vision returned empty response"
        return result
    except Exception as e:
        return f"❌ Screenshot or vision error: {e}"


# ── Fix Code on Screen ────────────────────────────────────────────
@function_tool()
async def fix_code_on_screen_vision() -> str:
    """Read and fix code on screen."""
    # FIX: Removed `import requests` — now uses urllib throughout (no extra dependency)
    def _do():
        img = _screenshot()
        code = _vision(img,
            "This is a code editor. Read ALL code exactly. "
            "Return ONLY raw code, no explanation, no backticks.")

        if not code or code.startswith("❌") or len(code.strip()) < 5:
            return f"❌ Could not read code: {code}"

        code = "\n".join(
            l for l in code.split("\n") if not l.strip().startswith("```")
        ).strip()

        key = os.getenv("GROQ_API_KEY", "")
        if not key:
            return "❌ GROQ_API_KEY missing"

        payload = json.dumps({
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user",
                          "content": f"Fix ALL bugs. Return ONLY corrected code:\n{code}"}],
            "max_tokens": 3000,
            "temperature": 0.2
        }).encode()

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                fixed = json.loads(r.read())["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            return f"❌ Groq API error {e.code}: {e.read().decode(errors='ignore')[:200]}"
        except Exception as ex:
            return f"❌ Groq request failed: {ex}"

        fixed = "\n".join(
            l for l in fixed.split("\n") if not l.strip().startswith("```")
        ).strip()

        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.2)
        pyperclip.copy(fixed)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.2)
        return "✅ Code fixed and replaced"

    try:
        return await asyncio.to_thread(_do)
    except Exception as e:
        return f"❌ {e}"