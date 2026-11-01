# ╔══════════════════════════════════════════════════════════════════╗
# ║  TIA AI — EMAIL                                                 ║
# ║  Handles: Gmail SMTP email sending                              ║
# ║  Setup: Add EMAIL_USER and EMAIL_PASS (App Password) to .env    ║
# ║  Copyright (c) 2025 Soham Ghadge                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio, os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from livekit.agents import function_tool

@function_tool()
async def send_email(to: str, subject: str, body: str) -> str:
    """Send email via Gmail SMTP."""
    def _do():
        user = os.getenv("EMAIL_USER","").strip()
        pw   = os.getenv("EMAIL_PASS","").strip()
        if not user or not pw:
            return "❌ EMAIL_USER and EMAIL_PASS missing in .env (use Gmail App Password)"
        try:
            msg = MIMEMultipart()
            msg["From"]=user; msg["To"]=to; msg["Subject"]=subject
            msg.attach(MIMEText(body,"plain"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                s.login(user, pw); s.send_message(msg)
            return f"✅ Email sent to {to}"
        except smtplib.SMTPAuthenticationError:
            return "❌ Auth failed — use Gmail App Password not main password"
        except Exception as e: return f"❌ {e}"
    return await asyncio.to_thread(_do)