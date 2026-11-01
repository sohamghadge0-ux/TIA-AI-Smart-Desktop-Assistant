# ╔══════════════════════════════════════════════════════════════════╗
# ║  TIA AI — WHATSAPP                                              ║
# ║  Handles: WhatsApp Web message sending                          ║
# ║  Numbers: wa.me direct link | Names: WhatsApp Web search        ║
# ║  Copyright (c) 2025 Soham Ghadge                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio, os, time, webbrowser
import pyautogui, pyperclip, requests
from livekit.agents import function_tool

@function_tool()
async def send_whatsapp_message(contact: str, message: str) -> str:
    """Send WhatsApp message to contact."""
    def _do():
        try:
            num = contact.replace("+","").replace(" ","").replace("-","")
            if num.isdigit():
                webbrowser.open(f"https://wa.me/{num}?text={requests.utils.quote(message)}")
                time.sleep(6); pyautogui.press("enter")
                return f"✅ Sent to {contact}"
            webbrowser.open("https://web.whatsapp.com/"); time.sleep(8)
            pyautogui.hotkey("ctrl","f"); time.sleep(1)
            pyperclip.copy(contact); pyautogui.hotkey("ctrl","v"); time.sleep(2)
            pyautogui.press("enter"); time.sleep(2)
            pyperclip.copy(message); pyautogui.hotkey("ctrl","v")
            time.sleep(0.8); pyautogui.press("enter")
            return f"✅ Sent to {contact}"
        except Exception as e: return f"❌ {e}"
    return await asyncio.to_thread(_do)