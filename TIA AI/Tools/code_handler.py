# ╔══════════════════════════════════════════════════════════════════╗
# ║  TIA AI — CODE & KNOWLEDGE HANDLER                              ║
# ║  Handles: Q&A, code gen, fix, essay, translate, AI image        ║
# ║  API: Groq LLM + Pollinations (images, free no key)             ║
# ║  Copyright (c) 2025 Soham Ghadge                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio, os, time, urllib.parse
import pyautogui, pyperclip, requests
from dotenv import load_dotenv
from livekit.agents import function_tool
load_dotenv()

def _groq(prompt: str, tokens: int = 2000) -> str:
    key = os.getenv("GROQ_API_KEY","").strip()
    if not key: return "❌ GROQ_API_KEY missing"
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json={"model":"llama-3.3-70b-versatile",
                  "messages":[{"role":"user","content":prompt}],
                  "max_tokens":tokens,"temperature":0.7},
            timeout=15)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except requests.Timeout: return "❌ Groq timeout — try again Boss"
    except Exception as e: return f"❌ {e}"

def _type(text: str):
    try: pyperclip.copy(text); time.sleep(0.15); pyautogui.hotkey("ctrl","v"); time.sleep(0.15)
    except: pass

def _clean(text: str) -> str:
    return "\n".join(l for l in text.split("\n") if not l.strip().startswith("```")).strip()

@function_tool()
async def answer_general_knowledge(question: str) -> str:
    """Answer any question like ChatGPT."""
    return await asyncio.to_thread(_groq,
        f"Answer clearly and concisely in 2-3 sentences:\n{question}", 500)

@function_tool()
async def explain_topic_in_detail(topic: str) -> str:
    """Explain any topic in detail."""
    return await asyncio.to_thread(_groq,
        f"Explain '{topic}' clearly — what it is, how it works, examples.", 700)

@function_tool()
async def get_health_medicine_info(query: str) -> str:
    """Get health medicine information."""
    return await asyncio.to_thread(_groq,
        f"Give helpful health info about: {query}\nEnd with: 'Doctor se milein Boss serious issues ke liye.'", 500)

@function_tool()
async def translate_text(text: str, target_language: str = "Hindi") -> str:
    """Translate text to any language."""
    def _do():
        result = _groq(f"Translate to {target_language}. Return ONLY translation:\n{text}", 600)
        if not result.startswith("❌"): _type(result)
        return result
    return await asyncio.to_thread(_do)

@function_tool()
async def summarize_text(text: str) -> str:
    """Summarize text in bullet points."""
    return await asyncio.to_thread(_groq, f"Summarize in 3-5 bullet points:\n{text}", 400)

@function_tool()
async def write_essay_or_content(topic: str, word_count: int = 150, content_type: str = "essay") -> str:
    """Write essay letter story and type on screen."""
    def _do():
        content = _groq(f"Write a {content_type} about '{topic}' in ~{word_count} words. Content only.", max(800,word_count*6))
        if content.startswith("❌"): return content
        _type(content)
        try:
            path = os.path.join(os.path.expanduser("~"),"Documents",f"{topic.replace(' ','_')[:30]}.txt")
            with open(path,"w",encoding="utf-8") as f: f.write(content)
        except: pass
        return f"✅ {content_type} typed and saved"
    return await asyncio.to_thread(_do)

@function_tool()
async def generate_and_type_code(description: str, language: str = "python") -> str:
    """Generate code and type on screen."""
    def _do():
        code = _groq(f"Write clean {language} code for: {description}\nReturn ONLY raw code.", 2000)
        if code.startswith("❌"): return code
        _type(_clean(code)); return f"✅ {language} code typed"
    return await asyncio.to_thread(_do)

@function_tool()
async def fix_code_error(error_description: str) -> str:
    """Fix code error and type on screen."""
    def _do():
        fixed = _groq(f"Fix this code/error. Return ONLY corrected code:\n{error_description}", 2000)
        if fixed.startswith("❌"): return fixed
        _type(_clean(fixed)); return "✅ Fixed code typed"
    return await asyncio.to_thread(_do)

@function_tool()
async def generate_ai_image(prompt: str) -> str:
    """Generate AI image from description."""
    def _do():
        try:
            url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true"
            r = requests.get(url, timeout=40); r.raise_for_status()
            path = os.path.join(os.path.expanduser("~"),"Pictures","tia_ai_image.jpg")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path,"wb") as f: f.write(r.content)
            os.startfile(path); return "✅ AI image generated and opened"
        except Exception as e: return f"❌ {e}"
    return await asyncio.to_thread(_do)