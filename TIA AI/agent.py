# ╔══════════════════════════════════════════════════════════════════╗
# ║           TIA AI — CORE ENGINE v3.0                             ║
# ║           Copyright (c) 2025 Soham Ghadge                       ║
# ╚══════════════════════════════════════════════════════════════════╝

from dotenv import load_dotenv
load_dotenv()

import asyncio, os, sys, socket, logging
from datetime import datetime
logging.basicConfig(level=logging.WARNING)

_MJ_DIR = os.path.dirname(os.path.abspath(__file__))
if _MJ_DIR not in sys.path:
    sys.path.insert(0, _MJ_DIR)

_tools_init = os.path.join(_MJ_DIR, 'Tools', '__init__.py')
if not os.path.exists(_tools_init):
    try:
        open(_tools_init, 'w').close()
    except Exception as e:
        print(f'⚠️ {e}')

def _net():
    try:
        s = socket.socket(); s.settimeout(3); s.connect(('8.8.8.8', 53)); s.close(); return True
    except: return False

_ONLINE = _net()
_llm_engine = None
if _ONLINE:
    try:
        from livekit.plugins.google.realtime import RealtimeModel
        _llm_engine = RealtimeModel
        print('✅ Google Realtime Model loaded!')
    except Exception as e:
        print(f'⚠️ {e}')
else:
    print('⚠️ Offline mode')

from livekit import agents
from livekit.agents import Agent, AgentSession, RoomInputOptions
from livekit.plugins import noise_cancellation
from prompts_tia import AGENT_INSTRUCTION, SESSION_INSTRUCTION

# ══════════════════════════════════════════════════════════════
#  SAFE IMPORT
# ══════════════════════════════════════════════════════════════
ALL_CAPABILITIES = []
_seen_tools = set()

def _safe_import(module, *names):
    results = []
    try:
        mod = __import__(f"Tools.{module}", fromlist=names)
        for name in names:
            try:
                fn = getattr(mod, name)
                if callable(fn) and fn.__name__ not in _seen_tools:
                    _seen_tools.add(fn.__name__)
                    results.append(fn)
            except AttributeError:
                pass
    except Exception:
        pass
    return results

def _add(*items):
    for item in items:
        if item and callable(item):
            ALL_CAPABILITIES.append(item)

# ══════════════════════════════════════════════════════════════
#  TOOLS — 66 cap, ordered by importance
# ══════════════════════════════════════════════════════════════

# 1. SYSTEM CONTROL (25 tools)
_add(*_safe_import("system_control",
    "open_app", "system_power_action",
    "control_screen_brightness", "control_system_volume",
    "create_file_or_folder", "delete_file_or_folder",
    "universal_file_opener", "search_files",
    "write_in_notepad", "screen_short",
    "type_text", "press_keyboard_shortcut",
    "scroll_up", "scroll_down",
    "maximize_window", "minimize_window",
    "close_window", "make_fullscreen",
    "go_back", "go_forward",
    "video_play_pause", "video_seek_forward",
    "video_seek_backward", "save_file",
    "desktop_control"))

# 2. SCREEN (3 tools) — total 28
_add(*_safe_import("screen_analyzer",
    "smart_screen_action",
    "analyze_screen",
    "fix_code_on_screen_vision"))

# 3. KNOWLEDGE & CODE (9 tools) — total 37
_add(*_safe_import("code_handler",
    "answer_general_knowledge",
    "explain_topic_in_detail",
    "get_health_medicine_info",
    "write_essay_or_content",
    "generate_and_type_code",
    "fix_code_error",
    "translate_text",
    "generate_ai_image",
    "summarize_text"))

# 4. MEDIA (8 tools) — total 45
_add(*_safe_import("youtube_videos",
    "play_media", "youtube_play_nth_result",
    "open_spotify", "spotify_search_play_quick",
    "spotify_next", "spotify_previous",
    "spotify_pause", "open_url"))

# 5. INFORMATION (5 tools) — total 50
_add(*_safe_import("information",
    "get_weather", "get_top_news",
    "get_time_info", "search_web",
    "get_global_info"))

# 6. COMMUNICATION (2 tools) — total 52
_add(*_safe_import("send_whatsapp_message", "send_whatsapp_message"))
_add(*_safe_import("send_email",            "send_email"))

# 7. MEMORY & REMINDERS (4 tools) — total 56
_add(*_safe_import("user_choice",
    "remember_fact", "recall_fact",
    "set_reminder", "save_user_preferences"))

# 8. SELF-LEARNING (3 tools) — total 59
_add(*_safe_import("tia_self_learn",
    "learn_from_user", "recall_memory",
    "search_and_answer"))

# 9. OFFICE (3 tools) — total 62
_add(*_safe_import("ms_office_handling",
    "create_word_document",
    "create_powerpoint_presentation",
    "create_excel_file"))

# 10. CREATE & DEV (2 tools) — total 64
_add(*_safe_import("website_maker",  "create_advanced_website"))
_add(*_safe_import("dev_tools",      "run_quick_command"))

# 11. EMOTION (2 tools) — total 66
_add(*_safe_import("emotion_detector",
    "detect_user_emotion", "analyze_voice_emotion"))

ALL_CAPABILITIES = ALL_CAPABILITIES[:66]
print(f"✅ TIA loaded {len(ALL_CAPABILITIES)} tools")


# ══════════════════════════════════════════════════════════════
#  MODEL — gemini-2.0-flash-live-001 is fastest + most stable
#  for realtime voice. 2.5 preview is slow and crashes.
# ══════════════════════════════════════════════════════════════
_MODELS = [
    'gemini-2.5-flash-native-audio-preview-12-2025',
    'gemini-2.0-flash-exp',
]

def _build_llm():
    if not _llm_engine:
        print("❌ No LLM engine available — is GOOGLE_API_KEY set and internet reachable?")
        return None
    for model in _MODELS:
        try:
            llm = _llm_engine(
                model=model,
                voice='Kore',
                temperature=0.6,
                max_output_tokens=1080,
            )
            print(f"✅ Using model: {model}")
            return llm
        except Exception as e:
            print(f"⚠️ Model {model} failed: {e}")
    print("❌ All models failed — check GOOGLE_API_KEY and quota")
    return None

def _build_prompt() -> str:
    try:
        from Tools.tia_self_learn import get_memory_context
        mem = get_memory_context()
    except: mem = ""
    return AGENT_INSTRUCTION + ("\n\n## TIA Memory:\n" + mem if mem else "")


# ══════════════════════════════════════════════════════════════
#  REMINDER ENGINE
# ══════════════════════════════════════════════════════════════
class ReminderEngine:
    def __init__(self):
        self._store = {}; self._counter = 0
        self._task = None; self._session = None

    def bind_session(self, s): self._session = s

    def schedule(self, text, trigger_time):
        rid = f'rem_{self._counter:04d}'; self._counter += 1
        self._store[rid] = {'text': text, 'time': trigger_time}
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._watch())
        return rid

    async def _watch(self):
        while self._store:
            try:
                now = datetime.now()
                for rid in [r for r, v in list(self._store.items()) if now >= v['time']]:
                    await self._fire(self._store.pop(rid))
                await asyncio.sleep(5)
            except Exception as e:
                print(f'🔔 {e}'); await asyncio.sleep(10)

    async def _fire(self, rem):
        try:
            if self._session:
                await self._session.generate_reply(
                    instructions=f"Boss ka reminder: {rem['text']}"
                )
        except Exception as e:
            print(f'🔔 fire: {e}')


# ══════════════════════════════════════════════════════════════
#  TIA ENGINE
# ══════════════════════════════════════════════════════════════
class TIAEngine(Agent):
    # FIX: llm is now passed in from outside so the same instance
    # is shared with AgentSession. Building it inside __init__ meant
    # AgentSession never got it — causing "no LLM model" crash.
    def __init__(self, llm):
        self.reminders = ReminderEngine()
        super().__init__(
            instructions=_build_prompt(),
            tools=ALL_CAPABILITIES,
            llm=llm,
        )
        print(f'✅ TIA Engine ready — {len(ALL_CAPABILITIES)} tools loaded')

    def attach_session(self, s):
        self._session = s
        self.reminders.bind_session(s)


# ══════════════════════════════════════════════════════════════
#  BUBBLE STATE
# ══════════════════════════════════════════════════════════════
def _bubble(state):
    try:
        import builtins
        b = getattr(builtins, 'tia_bubble', None)
        if b: b._state = state
    except: pass

async def _bubble_poller(session):
    prev = None
    while True:
        try:
            sp = session.current_speech is not None
            if sp != prev:
                _bubble("speaking" if sp else "idle"); prev = sp
        except: pass
        await asyncio.sleep(0.1)

async def _user_tracker(ctx, session):
    try:
        await asyncio.sleep(3)
        from livekit.rtc import TrackKind
        prev = False
        while True:
            try:
                us = any(
                    pub.track and pub.track.enabled
                    for p in ctx.room.remote_participants.values()
                    for pub in p.track_publications.values()
                    if pub.kind == TrackKind.KIND_AUDIO
                )
                if us != prev:
                    if us and session.current_speech is None:
                        _bubble("listening")
                    elif not us and session.current_speech is None:
                        _bubble("thinking")
                        await asyncio.sleep(1.5)
                        if session.current_speech is None:
                            _bubble("idle")
                    prev = us
            except: pass
            await asyncio.sleep(0.15)
    except Exception as e:
        print(f"Tracker: {e}")


# ══════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ══════════════════════════════════════════════════════════════
async def entrypoint(ctx: agents.JobContext):
    print('🚀 Starting TIA...')

    # FIX: Build LLM once here and pass it to BOTH TIAEngine and AgentSession.
    # Previously, LLM was built inside TIAEngine.__init__ and never reached
    # AgentSession — which is what actually drives the conversation in
    # livekit-agents v1.x. AgentSession without an LLM raises:
    # RuntimeError: trying to generate reply without an LLM model
    llm = _build_llm()
    if llm is None:
        print("❌ Cannot start — no LLM available. Check GOOGLE_API_KEY and internet connection.")
        return

    engine  = TIAEngine(llm)
    session = AgentSession(llm=llm)   # FIX: LLM must be passed here

    await session.start(
        room=ctx.room,
        agent=engine,
        room_input_options=RoomInputOptions(
            video_enabled=False,
            noise_cancellation=noise_cancellation.BVC()
        )
    )

    engine.attach_session(session)
    await ctx.connect()

    asyncio.create_task(_bubble_poller(session))
    asyncio.create_task(_user_tracker(ctx, session))

    await asyncio.sleep(0.15)
    await session.generate_reply(instructions=SESSION_INSTRUCTION)
    print('🔥 TIA IS LIVE!')

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        print('🛑 TIA session ended')


if __name__ == '__main__':
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))