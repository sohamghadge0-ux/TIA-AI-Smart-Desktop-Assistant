# ╔══════════════════════════════════════════════════════════════════╗
# ║  TIA AI — DEVELOPER TOOLS                                       ║
# ║  Handles: Running shell commands, returning output              ║
# ║  Copyright (c) 2025 Soham Ghadge                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio, subprocess
from livekit.agents import function_tool

@function_tool()
async def run_quick_command(command: str) -> str:
    """Run shell command return output."""
    def _do():
        try:
            p = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=20)
            out = (p.stdout or "").strip(); err = (p.stderr or "").strip()
            msg = f"Exit: {p.returncode}"
            if out: msg += f"\n{out[:800]}"
            if err: msg += f"\nError: {err[:400]}"
            return msg
        except subprocess.TimeoutExpired: return "❌ Command timed out"
        except Exception as e: return f"❌ {e}"
    return await asyncio.to_thread(_do)