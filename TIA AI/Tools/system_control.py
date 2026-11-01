# ╔══════════════════════════════════════════════════════════════════╗
# ║  TIA AI — SYSTEM CONTROL                                        ║
# ║  Handles: App launch, volume%, brightness%, keyboard, scroll,   ║
# ║  window, video controls, screenshot, files, desktop shortcuts   ║
# ║  Copyright (c) 2025 Soham Ghadge                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio, os, subprocess, time, glob, shutil, ctypes, threading
import pyautogui, pyperclip
from livekit.agents import function_tool

pyautogui.FAILSAFE = False
pyautogui.PAUSE    = 0.04

# ── App map ───────────────────────────────────────────────────────
_APP_MAP = {
    "chrome":"chrome","google chrome":"chrome","browser":"chrome",
    "firefox":"firefox","edge":"msedge","notepad":"notepad","notepad++":"notepad++",
    "word":"winword","excel":"excel","powerpoint":"powerpnt","outlook":"outlook",
    "teams":"teams","vscode":"code","vs code":"code","visual studio code":"code",
    "calculator":"calc","paint":"mspaint","explorer":"explorer",
    "file explorer":"explorer","task manager":"taskmgr","control panel":"control",
    "spotify":"spotify","discord":"discord","telegram":"telegram",
    "whatsapp":"whatsapp","zoom":"zoom","skype":"skype","vlc":"vlc",
    "cmd":"cmd","command prompt":"cmd","powershell":"powershell",
    "settings":"ms-settings:","store":"ms-windows-store:",
    "camera":"microsoft.windows.camera:","photos":"ms-photos:",
    "wordpad":"wordpad","snipping tool":"snippingtool","sticky notes":"stikynot",
}
_URI_APPS = {"settings","store","camera","photos"}

# ── Force a window to foreground by process name ──────────────────
def _force_foreground(exe_hint: str, delay: float = 1.2):
    try:
        time.sleep(delay)
        ps = (
            f'$proc = Get-Process | Where-Object {{$_.MainWindowHandle -ne 0 -and '
            f'($_.Name -like "*{exe_hint}*" -or $_.MainWindowTitle -ne "")}} | '
            f'Sort-Object StartTime -Descending | Select-Object -First 1; '
            f'if ($proc) {{ '
            f'  $hwnd = $proc.MainWindowHandle; '
            f'  Add-Type -TypeDefinition \'using System;using System.Runtime.InteropServices;'
            f'public class W{{[DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr h);'
            f'[DllImport("user32.dll")]public static extern bool ShowWindow(IntPtr h,int n);}}\'; '
            f'  [W]::ShowWindow($hwnd, 9); [W]::SetForegroundWindow($hwnd)'
            f'}}'
        )
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", ps],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"⚠️ foreground: {e}")

# ── Open App — 4 strategies ───────────────────────────────────────
def _open_app_sync(app_name: str) -> str:
    key = app_name.lower().strip()
    exe = _APP_MAP.get(key, "")
    errors = []

    if key in _URI_APPS or exe.endswith(":"):
        uri = exe if exe.endswith(":") else f"ms-{key}:"
        try:
            subprocess.Popen(["powershell","-Command",f'Start-Process "{uri}"'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            threading.Thread(target=_force_foreground, args=(key,), daemon=True).start()
            return f"✅ {app_name} opened"
        except Exception as e: errors.append(f"URI:{e}")

    if exe and not exe.endswith(":"):
        try:
            subprocess.Popen(exe, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            threading.Thread(target=_force_foreground, args=(exe.split()[0],), daemon=True).start()
            return f"✅ {app_name} opened"
        except FileNotFoundError: errors.append(f"exe '{exe}' not found")
        except Exception as e: errors.append(f"exe:{e}")

    if not exe:
        ps = (f'$a=Get-StartApps|Where-Object{{$_.Name -like "*{app_name}*"}}|Select-Object -First 1;'
              f'if($a){{Start-Process("shell:AppsFolder\\"+$a.AppID);Write-Output "OK:$($a.Name)"}}else{{Write-Output "NOTFOUND"}}')
        try:
            r = subprocess.run(["powershell","-Command",ps],
                capture_output=True, text=True, timeout=8)
            out = (r.stdout or "").strip()
            if out.startswith("OK:"):
                threading.Thread(target=_force_foreground, args=(app_name,), daemon=True).start()
                return f"✅ {out[3:]} opened"
            elif out == "NOTFOUND": errors.append("Not in Start Menu")
            else: errors.append(f"StartApps:'{out[:60]}'")
        except subprocess.TimeoutExpired: errors.append("StartApps timeout")
        except Exception as e: errors.append(f"StartApps:{e}")

    try:
        pyautogui.hotkey("win","s"); time.sleep(0.8)
        pyperclip.copy(app_name); pyautogui.hotkey("ctrl","v")
        time.sleep(1.0); pyautogui.press("enter")
        return f"✅ {app_name} launched via Start Search"
    except Exception as e: errors.append(f"Win+S:{e}")

    return f"❌ Could not open '{app_name}'.\n" + "\n".join(f"• {e}" for e in errors)

@function_tool()
async def open_app(app_name: str) -> str:
    """Open any app by name."""
    return await asyncio.to_thread(_open_app_sync, app_name)


# ── Power ─────────────────────────────────────────────────────────
@function_tool()
async def system_power_action(action: str) -> str:
    """Shutdown restart sleep lock logoff."""
    cmds = {"shutdown":"shutdown /s /t 5","restart":"shutdown /r /t 5",
            "sleep":"rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "lock":"rundll32.exe user32.dll,LockWorkStation","logoff":"shutdown /l"}
    cmd = cmds.get(action.lower())
    if not cmd: return f"❌ Unknown: {action}"
    await asyncio.to_thread(subprocess.run, cmd, shell=True)
    return f"✅ {action} initiated"


# ── Volume ────────────────────────────────────────────────────────
def _com_init():
    """
    FIX: Initialize COM on the current thread before using pycaw.
    asyncio.to_thread creates new worker threads that don't have COM
    initialized. Without this, pycaw crashes silently every time.
    """
    try:
        import comtypes
        comtypes.CoInitialize()
    except Exception:
        pass  # Already initialized on this thread — safe to ignore

def _get_vol() -> int:
    _com_init()  # FIX: must call before any pycaw usage
    try:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        dev = AudioUtilities.GetSpeakers()
        iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(iface, POINTER(IAudioEndpointVolume))
        return int(round(vol.GetMasterVolumeLevelScalar() * 100))
    except Exception as e:
        print(f"⚠️ _get_vol: {e}")
        return -1

def _set_vol_pycaw(p: int) -> str | None:
    _com_init()  # FIX: must call before any pycaw usage
    try:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        p = max(0, min(100, p))
        dev = AudioUtilities.GetSpeakers()
        iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(iface, POINTER(IAudioEndpointVolume))
        vol.SetMasterVolumeLevelScalar(p / 100.0, None)
        return f"✅ Volume {p}%"
    except ImportError:
        return None
    except Exception as e:
        return f"❌ {e}"

def _set_vol_keys(target: int) -> str:
    cur = _get_vol(); base = cur if cur >= 0 else 50
    target = max(0, min(100, target)); delta = target - base
    key = "volumeup" if delta > 0 else "volumedown"
    for _ in range(max(abs(delta) // 2, 1)):
        pyautogui.press(key); time.sleep(0.03)
    return f"✅ Volume ~{target}%"

@function_tool()
async def control_system_volume(action: str = "set", percent: int = 50) -> str:
    """Set increase decrease mute unmute volume percent."""
    def _do():
        a = action.lower().strip()
        p = max(0, min(100, percent))

        if a in ("mute", "unmute"):
            pyautogui.press("volumemute")
            return f"✅ {'Muted' if a == 'mute' else 'Unmuted'}"

        if any(w in a for w in ("increase","up","raise","badh","add","plus")):
            cur = _get_vol(); target = min(100, (cur if cur >= 0 else 50) + p)
        elif any(w in a for w in ("decrease","down","reduce","lower","ghat","minus","less","kam")):
            cur = _get_vol(); target = max(0, (cur if cur >= 0 else 50) - p)
        elif a in ("set", "to"):
            target = p
        else:
            # FIX: log unrecognized action instead of silently proceeding
            print(f"⚠️ Unrecognized volume action '{a}', treating as set to {p}%")
            target = p

        r = _set_vol_pycaw(target)
        return r if r is not None else _set_vol_keys(target)

    return await asyncio.to_thread(_do)


# ── Brightness ────────────────────────────────────────────────────
@function_tool()
async def control_screen_brightness(action: str = "set", percent: int = 70) -> str:
    """Set increase decrease screen brightness percent."""
    def _do():
        a = action.lower().strip()
        p = max(0, min(100, percent))

        # FIX: include Hinglish words to match volume tool consistency
        is_increase = any(w in a for w in ("increase","up","raise","badh","add","plus"))
        is_decrease = any(w in a for w in ("decrease","down","reduce","lower","ghat","minus","less","kam"))

        if is_increase or is_decrease:
            cur = 70  # safe default
            try:
                # FIX: Get-WmiObject is deprecated/removed in PS7+.
                # Use Get-CimInstance instead — works on all modern Windows.
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"],
                    capture_output=True, text=True, timeout=5
                )
                lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
                for line in reversed(lines):
                    if line.isdigit():
                        cur = int(line); break
                if res.returncode != 0 and res.stderr.strip():
                    print(f"⚠️ brightness get: {res.stderr.strip()[:120]}")
            except Exception as e:
                print(f"⚠️ brightness get: {e}")
            new = min(100, cur + p) if is_increase else max(0, cur - p)
        else:
            new = p

        # FIX: Get-WmiObject → Get-CimInstance for SET too.
        # FIX: capture_output=True so errors are logged, not swallowed.
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods)"
                 f".WmiSetBrightness(1,{new})"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode != 0:
                err = res.stderr.strip()
                if err:
                    return f"❌ Brightness set failed: {err[:200]}"
        except subprocess.TimeoutExpired:
            return "❌ Brightness command timed out"
        except Exception as e:
            return f"❌ Brightness error: {e}"

        return f"✅ Brightness {new}%"

    try:
        return await asyncio.to_thread(_do)
    except Exception as e:
        return f"❌ {e}"


# ── Files ─────────────────────────────────────────────────────────
@function_tool()
async def create_file_or_folder(name: str, location: str = "Desktop", item_type: str = "folder") -> str:
    """Create file or folder."""
    locs = {"desktop":os.path.join(os.path.expanduser("~"),"Desktop"),
            "documents":os.path.join(os.path.expanduser("~"),"Documents"),
            "downloads":os.path.join(os.path.expanduser("~"),"Downloads")}
    base = locs.get(location.lower(), location)
    path = os.path.join(base, name)
    try:
        if item_type.lower() == "folder": os.makedirs(path, exist_ok=True)
        else:
            with open(path, "w") as f: f.write("")
        return f"✅ Created {item_type}: {path}"
    except Exception as e: return f"❌ {e}"

@function_tool()
async def delete_file_or_folder(path: str) -> str:
    """Delete file or folder."""
    try:
        if not os.path.exists(path):
            m = glob.glob(f"C:/Users/**/{path}", recursive=True)[:1]
            if m: path = m[0]
            else: return f"❌ Not found: {path}"
        if os.path.isdir(path): shutil.rmtree(path)
        else: os.remove(path)
        return f"✅ Deleted: {path}"
    except Exception as e: return f"❌ {e}"

@function_tool()
async def universal_file_opener(file_path: str) -> str:
    """Open file with default app."""
    try:
        if os.path.exists(file_path):
            await asyncio.to_thread(os.startfile, file_path); return "✅ Opened"
        m = glob.glob(f"C:/Users/**/{file_path}", recursive=True)[:1]
        if m: await asyncio.to_thread(os.startfile, m[0]); return f"✅ Opened: {m[0]}"
        return f"❌ Not found: {file_path}"
    except Exception as e: return f"❌ {e}"

@function_tool()
async def search_files(query: str) -> str:
    """Search files by name."""
    def _do():
        r = []
        try:
            for m in glob.glob(f"{os.path.expanduser('~')}/**/*{query}*", recursive=True)[:5]:
                r.append(m)
        except: pass
        return "\n".join(r) if r else f"No files matching '{query}'"
    return await asyncio.to_thread(_do)

@function_tool()
async def write_in_notepad(content: str, filename: str = "tia_note.txt") -> str:
    """Write text to file and open."""
    path = os.path.join(os.path.expanduser("~"), "Documents", filename)
    with open(path, "w", encoding="utf-8") as f: f.write(content)
    await asyncio.to_thread(os.startfile, path)
    return f"✅ Saved: {path}"


# ── Keyboard ──────────────────────────────────────────────────────
@function_tool()
async def type_text(text: str) -> str:
    """Type text at cursor."""
    def _do(): pyperclip.copy(text); time.sleep(0.15); pyautogui.hotkey("ctrl","v"); time.sleep(0.15)
    await asyncio.to_thread(_do); return "✅ Typed"

@function_tool()
async def press_keyboard_shortcut(shortcut: str) -> str:
    """Press keyboard shortcut like ctrl+c."""
    keys = shortcut.lower().replace(" ","").split("+")
    await asyncio.to_thread(pyautogui.hotkey, *keys); return f"✅ {shortcut}"

@function_tool()
async def save_file() -> str:
    """Save current file."""
    await asyncio.to_thread(pyautogui.hotkey,"ctrl","s"); return "✅ Saved"


# ── Scroll ────────────────────────────────────────────────────────
@function_tool()
async def scroll_up(amount: int = 3) -> str:
    """Scroll up."""
    await asyncio.to_thread(pyautogui.scroll, amount*100); return "✅ Scrolled up"

@function_tool()
async def scroll_down(amount: int = 3) -> str:
    """Scroll down."""
    await asyncio.to_thread(pyautogui.scroll, -amount*100); return "✅ Scrolled down"


# ── Windows ───────────────────────────────────────────────────────
@function_tool()
async def maximize_window() -> str:
    """Maximize current window."""
    await asyncio.to_thread(pyautogui.hotkey,"win","up"); return "✅ Maximized"

@function_tool()
async def minimize_window() -> str:
    """Minimize current window."""
    await asyncio.to_thread(pyautogui.hotkey,"win","down"); return "✅ Minimized"

@function_tool()
async def close_window() -> str:
    """Close current window."""
    await asyncio.to_thread(pyautogui.hotkey,"alt","f4"); return "✅ Closed"

@function_tool()
async def make_fullscreen() -> str:
    """Toggle fullscreen F11."""
    await asyncio.to_thread(pyautogui.press,"f11"); return "✅ Fullscreen"

@function_tool()
async def go_back() -> str:
    """Browser go back."""
    await asyncio.to_thread(pyautogui.hotkey,"alt","left"); return "✅ Back"

@function_tool()
async def go_forward() -> str:
    """Browser go forward."""
    await asyncio.to_thread(pyautogui.hotkey,"alt","right"); return "✅ Forward"


# ── Video ─────────────────────────────────────────────────────────
@function_tool()
async def video_play_pause() -> str:
    """Play or pause video."""
    await asyncio.to_thread(pyautogui.press,"k"); return "✅ Play/Pause"

@function_tool()
async def video_seek_forward(seconds: int = 10) -> str:
    """Seek video forward by seconds."""
    def _do():
        for _ in range(max(1,seconds//5)): pyautogui.press("right"); time.sleep(0.05)
    await asyncio.to_thread(_do); return f"✅ +{seconds}s"

@function_tool()
async def video_seek_backward(seconds: int = 10) -> str:
    """Seek video backward by seconds."""
    def _do():
        for _ in range(max(1,seconds//5)): pyautogui.press("left"); time.sleep(0.05)
    await asyncio.to_thread(_do); return f"✅ -{seconds}s"


# ── Screenshot ────────────────────────────────────────────────────
@function_tool()
async def screen_short() -> str:
    """Take screenshot."""
    def _do():
        import datetime
        path = os.path.join(os.path.expanduser("~"),"Desktop",
            f"tia_{datetime.datetime.now().strftime('%H%M%S')}.png")
        pyautogui.screenshot(path); return path
    try:
        path = await asyncio.to_thread(_do); return f"✅ Saved: {path}"
    except Exception as e: return f"❌ {e}"


# ── Desktop ───────────────────────────────────────────────────────
@function_tool()
async def desktop_control(action: str) -> str:
    """Desktop shortcut show_desktop task_view search run."""
    acts = {"show_desktop":("win","d"),"task_view":("win","tab"),
            "search":("win","s"),"run":("win","r"),
            "action_center":("win","a"),"notifications":("win","n")}
    keys = acts.get(action.lower())
    if keys: await asyncio.to_thread(pyautogui.hotkey,*keys); return f"✅ {action}"
    return f"❌ Unknown: {action}"