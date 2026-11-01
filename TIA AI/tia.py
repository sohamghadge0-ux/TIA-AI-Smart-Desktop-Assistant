# ╔══════════════════════════════════════════════════════════╗
# ║              TIA AI - MAIN APPLICATION                   ║
# ║  Copyright (c) 2025 Soham Ghadge — All Rights Reserved  ║
# ║  Product: TIA AI  Version: 2.0.0  Year: 2025            ║
# ╚══════════════════════════════════════════════════════════╝

import sys, math, os, json, traceback, time, socket, threading, logging, random
import numpy as np

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLineEdit,
    QPushButton, QHBoxLayout, QLabel, QMenu, QMessageBox, QInputDialog,
    QDialog, QProgressBar, QDialogButtonBox, QAction, QGraphicsOpacityEffect)
from PyQt5.QtCore  import QTimer, Qt, QPointF, QRectF, QPropertyAnimation, QSize, \
                           QEasingCurve, QParallelAnimationGroup, QSequentialAnimationGroup
from PyQt5.QtGui   import (QPainter, QPen, QBrush, QColor, QFont, QFontMetrics,
    QLinearGradient, QRadialGradient, QPainterPath, QCursor)

from agent import entrypoint
import firebase_admin
from firebase_admin import credentials, db

logging.getLogger('asyncio').setLevel(logging.WARNING)


# ───────────────────────────────────────────────────────────────
#  HELPERS
# ───────────────────────────────────────────────────────────────
def _ac(color: QColor, alpha: float) -> QColor:
    c = QColor(color); c.setAlphaF(max(0.0, min(1.0, alpha))); return c

def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t)); return 1.0 - (1.0 - t) ** 3


# ───────────────────────────────────────────────────────────────
#  BUBBLE STATE WIRING
# ───────────────────────────────────────────────────────────────
def _wire_bubble_states():
    try:
        from livekit.agents import AgentSession
        _orig_start = AgentSession.start

        async def _patched_start(sess, *args, **kwargs):
            import builtins

            def _set(state):
                b = getattr(builtins, 'tia_bubble', None)
                if b: b._state = state

            event_map = {
                "user_speech_started":     "listening",
                "user_speech_committed":   "thinking",
                "agent_speech_started":    "speaking",
                "agent_speech_committed":  "idle",
                "agent_speech_interrupted":"listening",
                "user_started_speaking":   "listening",
                "user_stopped_speaking":   "thinking",
                "agent_started_speaking":  "speaking",
                "agent_stopped_speaking":  "idle",
                "input_speech_started":    "listening",
                "input_speech_committed":  "thinking",
                "output_speech_started":   "speaking",
                "output_speech_committed": "idle",
            }
            for evt, state in event_map.items():
                try: sess.on(evt)(lambda *_, s=state: _set(s))
                except: pass

            return await _orig_start(sess, *args, **kwargs)

        AgentSession.start = _patched_start
        print("✅ Bubble state wiring ready")
    except Exception as e:
        print(f"Bubble wiring note: {e}")

_wire_bubble_states()


# ═══════════════════════════════════════════════════════════════
#  ANIME OS BOOT SCREEN  — FASTER (3.5s total instead of 7.6s)
# ═══════════════════════════════════════════════════════════════
class TIABootScreen(QWidget):

    CYAN  = QColor(0, 200, 255)
    WHITE = QColor(255, 255, 255)
    BG    = QColor(0, 6, 14)
    DIM   = QColor(0, 60, 80)

    # ── FASTER TIMINGS: start_ms cut in half, duration cut to 200ms ──
    CHECKS = [
        ("NEURAL CORE INITIALIZATION",   800,  200),
        ("LIVEKIT SERVER HANDSHAKE",     1100,  200),
        ("GEMINI REALTIME LINK",         1400,  200),
        ("LOADING CAPABILITY MODULES",   1700,  200),
        ("ACTIVATION SIGNATURE VERIFIED",2000,  200),
        ("SYSTEM FULLY OPERATIONAL",     2300,  200),
    ]
    FINISH_MS = 3200   # was 7600 — now 3.2s total
    FADE_MS   = 500    # was 900

    def __init__(self):
        super().__init__()
        self._ms = 0; self._fade_t = 0.0; self._fading = False
        self._arc1 = 0.0; self._arc2 = 0.0; self._arc3 = 0.0
        self._check_t = [0.0] * len(self.CHECKS)
        self._on_done = None; self._bar_scroll = 0.0
        self._hex_pts = []
        self._build_hex()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet("background:#00060e;")
        self.setGeometry(QApplication.primaryScreen().geometry())
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_on_done(self, cb): self._on_done = cb

    def _build_hex(self):
        S = 28; H = S * math.sqrt(3) / 2
        for row in range(-1, 45):
            for col in range(-1, 75):
                x = col * S * 1.5
                y = row * H * 2 + (H if col % 2 else 0)
                self._hex_pts.append([
                    QPointF(x + S*math.cos(math.radians(60*i-30)),
                            y + S*math.sin(math.radians(60*i-30)))
                    for i in range(6)
                ])

    def _tick(self):
        self._ms += 16
        for i, (_, s, d) in enumerate(self.CHECKS):
            self._check_t[i] = _ease_out((self._ms - s) / d)
        self._arc1 = (self._arc1 + 2.0) % 360
        self._arc2 = (self._arc2 - 1.3) % 360
        self._arc3 = (self._arc3 + 0.6) % 360
        self._bar_scroll += 0.4
        if self._ms >= self.FINISH_MS and not self._fading:
            self._fading = True
        if self._fading:
            self._fade_t = min(1.0, self._fade_t + 16/self.FADE_MS)
            if self._fade_t >= 1.0:
                self._timer.stop(); self.close()
                if self._on_done: self._on_done()
        self.update()

    def _t(self, s, d=200):   # default duration faster
        return _ease_out((self._ms - s) / d)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        W = self.width(); H = self.height()
        cx = W//2; cy = H//2
        p.setOpacity(1.0 - self._fade_t)

        # BG
        p.fillRect(0, 0, W, H, self.BG)

        # Hex grid
        ha = min(0.13, self._t(100, 400)*0.13)
        if ha > 0:
            p.setPen(QPen(_ac(self.CYAN, ha), 0.5)); p.setBrush(Qt.NoBrush)
            for pts in self._hex_pts:
                for i in range(6): p.drawLine(pts[i], pts[(i+1)%6])

        # Vignette
        vg = QRadialGradient(cx, cy, max(W,H)*0.65)
        vg.setColorAt(0.0, QColor(0,0,0,0)); vg.setColorAt(1.0, QColor(0,4,10,200))
        p.setBrush(QBrush(vg)); p.setPen(Qt.NoPen); p.drawRect(0,0,W,H)

        # Data streams
        st = self._t(100, 300)
        if st > 0:
            sf = QFont("Courier New",8); p.setFont(sf); sfm = QFontMetrics(sf)
            lbls = ["SYS_INIT","MEM_ALLOC","GPU_LINK","NET_AUTH","KEY_VFY","MODULE_LD",
                    "API_KEY","VOICE_RDY","TOKEN","HASH","CERT","SESS_ID","AI_BOOT",
                    "PREM_VLD","SYNC","ACK","PING","LIVE","CAM_OK","SCR_ON"]
            hx = "0123456789ABCDEF"; lh=15; sw=148
            for side in [0,1]:
                sx = 14 if side==0 else W-sw-14
                for i,lbl in enumerate(lbls):
                    val = "".join(random.choice(hx) for _ in range(8))
                    ry = ((i*lh - int(self._bar_scroll*0.5)) % (20*lh)) + lh
                    p.setPen(_ac(self.CYAN, st*0.17))
                    txt = f"{lbl}: {val}"
                    if side==1: p.drawText(sx+sw-sfm.horizontalAdvance(txt), ry, txt)
                    else: p.drawText(sx, ry, txt)

        # Side borders
        if st > 0:
            p.setPen(QPen(_ac(self.CYAN, st*0.07),1))
            p.drawLine(162,0,162,H); p.drawLine(W-162,0,W-162,H)

        # Corner brackets
        bt = self._t(100, 300)
        if bt > 0:
            bl=int(bt*110); bo=22
            p.setPen(QPen(_ac(self.CYAN, bt*0.8),1.5)); p.setBrush(Qt.NoBrush)
            for bx,by,sx,sy in [(bo,bo,1,1),(W-bo,bo,-1,1),(bo,H-bo,1,-1),(W-bo,H-bo,-1,-1)]:
                p.drawLine(bx,by,bx+sx*bl,by); p.drawLine(bx,by,bx,by+sy*bl)

        # Corner tags
        tt = self._t(300, 300)
        if tt > 0:
            tf = QFont("Courier New",8); tf.setLetterSpacing(QFont.AbsoluteSpacing,0.5)
            p.setFont(tf); p.setPen(_ac(self.CYAN,tt*0.42))
            tfm=QFontMetrics(tf); lh2=16; bo2=38
            for i,t in enumerate(["SYSTEM_ID: TIA-2025","NODE: PREMIUM","OWNER: SOHAM.G","AUTH: ACTIVE"]):
                p.drawText(bo2, bo2+i*lh2, t)
            for i,t in enumerate(["MEMORY: 8192MB","GPU: ENGAGED","NETWORK: SECURED","PING: <20MS"]):
                p.drawText(W-bo2-tfm.horizontalAdvance(t), bo2+i*lh2, t)
            for i,t in enumerate(["VERSION: 2.0.0","BUILD: 20250314","AI: GEMINI-2.0","MODE: REALTIME"]):
                p.drawText(bo2, H-bo2-(3-i)*lh2, t)
            for i,t in enumerate(["TOOLS: 50 LOADED","VOICE: ONLINE","VISION: ACTIVE"]):
                p.drawText(W-bo2-tfm.horizontalAdvance(t), H-bo2-(2-i)*lh2, t)

        # Orbit rings + dots
        for (rr,alpha,rt),arc in zip(
            [(260,0.14,self._t(200,300)),(200,0.08,self._t(300,300)),(150,0.22,self._t(400,300))],
            [self._arc1,self._arc2,self._arc3]
        ):
            if rt<=0: continue
            p.setPen(QPen(_ac(self.CYAN,rt*alpha),1.0)); p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(cx-rr*rt,cy-rr*rt,rr*rt*2,rr*rt*2))
            da=math.radians(arc)
            p.setBrush(QBrush(_ac(self.CYAN,rt*0.85))); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx+rr*rt*math.cos(da),cy+rr*rt*math.sin(da)),3.5,3.5)

        # Spinning arcs
        at = self._t(400, 200)
        if at > 0:
            for rad,am,arc,span in [(140,0.88,self._arc1,100),(150,0.30,self._arc2,80),(155,0.15,self._arc3,60)]:
                pen=QPen(_ac(self.CYAN,at*am),1.5 if am>0.5 else 0.8)
                pen.setCapStyle(Qt.RoundCap); p.setPen(pen); p.setBrush(Qt.NoBrush)
                p.drawArc(QRectF(cx-rad,cy-rad,rad*2,rad*2),int(arc*16),span*16)

        # Scan sweep
        swt=(self._ms-100)/600.0
        if 0<swt<1.0:
            sy=int(swt*H)
            sg=QLinearGradient(0,sy-2,0,sy+3)
            sg.setColorAt(0,QColor(0,0,0,0)); sg.setColorAt(0.5,_ac(self.CYAN,0.9))
            sg.setColorAt(1,QColor(0,0,0,0))
            p.setBrush(QBrush(sg)); p.setPen(Qt.NoPen); p.drawRect(0,sy-2,W,5)

        # TIA Logo
        lf=QFont("Arial",100,QFont.Black); p.setFont(lf); lfm=QFontMetrics(lf)
        chars=['T','I','A']
        total=sum(lfm.horizontalAdvance(c) for c in chars)+10
        lx=cx-total//2; ly=cy-30
        for i,ch in enumerate(chars):
            lt=_ease_out((self._ms-(500+i*100))/250.0)
            if lt<=0: continue
            p.setPen(QColor(255,255,255,int(lt*225)))
            p.drawText(lx, ly-int((1-lt)*22), ch)
            lx+=lfm.horizontalAdvance(ch)+(4 if i<2 else 0)
        if self._ms>800 and random.random()<0.07:
            gfm=QFontMetrics(QFont("Arial",100,QFont.Black))
            p.setPen(_ac(self.CYAN,0.45))
            p.drawText(cx-gfm.horizontalAdvance("TIA")//2+random.randint(-8,8),ly-4,"TIA")

        # Subtitle
        subt=self._t(900, 200)
        if subt>0:
            sf2=QFont("Arial",12); sf2.setLetterSpacing(QFont.AbsoluteSpacing,8)
            p.setFont(sf2); p.setPen(_ac(self.CYAN,subt*0.68))
            stxt="TOTAL INTELLIGENCE ASSISTANT"
            p.drawText(cx-QFontMetrics(sf2).horizontalAdvance(stxt)//2, ly+46, stxt)

        # Divider
        divt=self._t(1000, 200)
        if divt>0:
            p.setPen(QPen(_ac(self.CYAN,divt*0.38),1))
            dw=int(divt*400); p.drawLine(cx-dw//2,ly+68,cx+dw//2,ly+68)

        # Check rows
        cf=QFont("Courier New",10); cf.setLetterSpacing(QFont.AbsoluteSpacing,1.8)
        p.setFont(cf); cfm=QFontMetrics(cf)
        rh=24; cy0=ly+88
        for i,(lbl,_,__) in enumerate(self.CHECKS):
            t=self._check_t[i]
            if t<=0: continue
            ry=cy0+i*rh; done=t>=1.0
            bx=cx-200; bs=14
            p.setPen(QPen(_ac(self.CYAN,t*(0.75 if done else 0.22)),1))
            p.setBrush(QBrush(_ac(self.CYAN,0.10 if done else 0.0)))
            p.drawRect(bx,ry-bs+2,bs,bs)
            if done:
                p.setPen(Qt.NoPen); p.setBrush(QBrush(_ac(self.CYAN,0.9)))
                p.drawRect(bx+4,ry-bs+6,6,6)
            tc=QColor(0,255,160,220) if (i==len(self.CHECKS)-1 and done) else _ac(self.CYAN,t*(0.9 if done else 0.38))
            p.setPen(tc)
            p.drawText(bx+bs+10,ry,lbl+(" ✓" if done else "..."))
            p.setPen(_ac(self.CYAN,t*0.18))
            nm=f"0{i+1}/06"; p.drawText(cx+200-cfm.horizontalAdvance(nm),ry,nm)

        # Progress bar
        prt=self._t(1000, 200)
        if prt>0:
            fill=sum(1 for t in self._check_t if t>=1.0)/len(self.CHECKS)
            bw=400; bh=2; bx=cx-bw//2; by=cy0+len(self.CHECKS)*rh+16
            p.setPen(Qt.NoPen); p.setBrush(QBrush(QColor(0,25,35))); p.drawRoundedRect(bx,by,bw,bh,1,1)
            if fill>0:
                fw=int(fill*bw)
                p.setBrush(QBrush(_ac(self.CYAN,prt))); p.drawRoundedRect(bx,by,fw,bh,1,1)
                p.setBrush(QBrush(_ac(self.WHITE,prt*0.9))); p.drawEllipse(QPointF(bx+fw,by+bh/2),3,3)
            pf=QFont("Courier New",8); pf.setLetterSpacing(QFont.AbsoluteSpacing,2); p.setFont(pf)
            p.setPen(_ac(self.CYAN,prt*0.8))
            pt=f"{int(fill*100)}%"; p.drawText(cx+bw//2+10,by+bh,pt)

        # Bottom bar
        bbt=self._t(800, 200)
        if bbt>0:
            p.setPen(QPen(_ac(self.CYAN,bbt*0.09),1)); p.drawLine(0,H-30,W,H-30)
            bbf=QFont("Courier New",8); bbf.setLetterSpacing(QFont.AbsoluteSpacing,1.5)
            p.setFont(bbf); p.setPen(_ac(self.CYAN,bbt*0.28))
            bbfm=QFontMetrics(bbf); bx2=28
            for itm in ["TIA OS v2.0","◆","PREMIUM EDITION","◆","SECURED ■"]:
                p.drawText(bx2,H-12,itm); bx2+=bbfm.horizontalAdvance(itm)+20

        # Version
        vt=self._t(600, 200)
        if vt>0:
            vf=QFont("Courier New",8); vf.setLetterSpacing(QFont.AbsoluteSpacing,2); p.setFont(vf)
            p.setPen(_ac(self.DIM,vt*0.7))
            vtxt="v2.0  //  SOHAM GHADGE  //  2025"
            p.drawText(W-QFontMetrics(vf).horizontalAdvance(vtxt)-22,H-12,vtxt)
        p.end()


# ═══════════════════════════════════════════════════════════════
#  TIA BUBBLE
# ═══════════════════════════════════════════════════════════════
BUBBLE_THEMES = {
    "idle":      {"primary": QColor(0,   200, 255), "spd": 0.020, "label": "IDLE"},
    "listening": {"primary": QColor(130,  70, 255), "spd": 0.034, "label": "LISTENING"},
    "speaking":  {"primary": QColor(0,   215, 140), "spd": 0.062, "label": "SPEAKING"},
    "thinking":  {"primary": QColor(240, 155,   0), "spd": 0.028, "label": "THINKING"},
}
_BW=170; _BH=196; _BR=62; _BCX=_BW//2; _BCY=_BR+18


class ModernFloatingWindow(QWidget):

    def __init__(self):
        super().__init__()
        print("🎯 TIA Bubble INIT")
        self._state    = "idle"
        self._pulse    = [0.0, 0.33, 0.66]
        self._arc1     = 0.0
        self._arc2     = 0.0
        self._arc3     = 0.0
        self._wave     = [0.0] * 7
        self._drag_pos = None

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFixedSize(_BW, _BH)
        self.setAttribute(Qt.WA_AcceptTouchEvents, False)
        self.setMouseTracking(True)

        desk = QApplication.primaryScreen().availableGeometry()
        self.move(desk.width()-_BW-24, desk.height()-_BH-48)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        import builtins
        builtins.tia_bubble = self
        print("🎯 TIA Bubble READY")

    def set_state(self, state: str):
        if state in BUBBLE_THEMES:
            QTimer.singleShot(0, lambda s=state: self._do_set(s))

    def _do_set(self, state: str):
        self._state = state

    def start_agent(self):
        def _run():
            try:
                print("🟡 Agent thread starting...")
                time.sleep(0.5)  # reduced from 1s
                import signal
                signal.signal = lambda *a, **kw: None
                sys.argv = ['agent', 'console']
                from livekit.agents.cli import run_app
                from livekit.agents import WorkerOptions
                run_app(WorkerOptions(entrypoint_fnc=entrypoint))
            except Exception as e:
                print(f"❌ Agent error: {e}"); traceback.print_exc()
        t = threading.Thread(target=_run, daemon=True, name="TIA-Agent")
        t.start()
        print("🔧 Agent thread started")

    def _tick(self):
        spd = BUBBLE_THEMES[self._state]["spd"]
        for i in range(3): self._pulse[i] = (self._pulse[i]+spd) % 1.0
        self._arc1 = (self._arc1+2.2) % 360
        self._arc2 = (self._arc2-1.4) % 360
        self._arc3 = (self._arc3+0.7) % 360
        if self._state == "speaking":
            for i in range(7): self._wave[i] = (self._wave[i]+0.08+i*0.012) % (2*math.pi)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        th = BUBBLE_THEMES[self._state]; pr = th["primary"]

        for phase in self._pulse:
            rr=_BR+8+phase*30; alpha=max(0.0,0.55*(1.0-phase))
            p.setPen(QPen(_ac(pr,alpha),1.0)); p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(_BCX-rr,_BCY-rr,rr*2,rr*2))

        p.setPen(QPen(_ac(pr,0.18),0.6)); r3=_BR+18
        p.drawArc(QRectF(_BCX-r3,_BCY-r3,r3*2,r3*2),int(self._arc3*16),60*16)
        p.setPen(QPen(_ac(pr,0.32),0.8)); r2=_BR+10
        p.drawArc(QRectF(_BCX-r2,_BCY-r2,r2*2,r2*2),int(self._arc2*16),80*16)
        pen=QPen(_ac(pr,0.88),1.5); pen.setCapStyle(Qt.RoundCap); p.setPen(pen)
        r1=_BR+3; p.drawArc(QRectF(_BCX-r1,_BCY-r1,r1*2,r1*2),int(self._arc1*16),95*16)

        p.setPen(Qt.NoPen); p.setBrush(QBrush(QColor(2,8,18,245)))
        p.drawEllipse(QRectF(_BCX-_BR,_BCY-_BR,_BR*2,_BR*2))
        p.setPen(QPen(_ac(pr,0.10),1)); p.setBrush(Qt.NoBrush)
        ri=_BR-8; p.drawEllipse(QRectF(_BCX-ri,_BCY-ri,ri*2,ri*2))
        p.setPen(QPen(_ac(pr,0.72),1.5))
        p.drawEllipse(QRectF(_BCX-_BR+1,_BCY-_BR+1,_BR*2-2,_BR*2-2))

        fnt=QFont("Arial",26,QFont.Bold); p.setFont(fnt)
        p.setPen(QColor(255,255,255,228)); fm=QFontMetrics(fnt)
        tw=fm.horizontalAdvance("TIA"); ty=_BCY+fm.ascent()//2-4
        p.drawText(_BCX-tw//2,ty,"TIA")

        if self._state=="speaking":
            hm=[5,12,8,16,6,10,5]; bw=3
            tw2=len(hm)*bw+(len(hm)-1)*3; bx=_BCX-tw2//2; bby=_BCY+30
            for i,h in enumerate(hm):
                amp=(math.sin(self._wave[i])+1)/2
                bh=max(3,int(h*(0.25+0.75*amp)))
                p.setPen(Qt.NoPen); p.setBrush(QBrush(_ac(pr,0.85)))
                p.drawRoundedRect(bx+i*(bw+3),bby-bh,bw,bh,1,1)
        else:
            da=0.3+0.7*abs(math.sin(self._pulse[0]*math.pi))
            p.setPen(Qt.NoPen); p.setBrush(QBrush(_ac(pr,da)))
            p.drawEllipse(QRectF(_BCX-4,_BCY+26,8,8))

        lf=QFont("Courier New",7); lf.setLetterSpacing(QFont.AbsoluteSpacing,2.5)
        p.setFont(lf); lbl=th["label"]; p.setPen(_ac(pr,0.55))
        lfm=QFontMetrics(lf); lw=lfm.horizontalAdvance(lbl)
        p.drawText(_BCX-lw//2,_BCY+_BR+24,lbl)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            menu = QMenu()
            menu.setStyleSheet("""
                QMenu { background-color: rgb(2, 10, 20); border: 1px solid rgba(0, 200, 255, 100); border-radius: 6px; padding: 4px 0px; }
                QMenu::item { font-family: Courier New; font-size: 12px; color: rgb(255, 80, 80); padding: 10px 24px; min-width: 140px; }
                QMenu::item:selected { background-color: rgba(255, 50, 50, 40); color: rgb(255, 120, 120); }
            """)
            close_action = menu.addAction("✕   Close TIA")
            chosen = menu.exec_(e.globalPos())
            if chosen == close_action:
                QApplication.quit()
            return
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
            self.setCursor(QCursor(Qt.ClosedHandCursor))

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(e.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, _):
        self._drag_pos = None
        self.setCursor(QCursor(Qt.ArrowCursor))

    def close_application(self): QApplication.quit()


# ═══════════════════════════════════════════════════════════════
#  FIREBASE & ACTIVATION  (unchanged from original)
# ═══════════════════════════════════════════════════════════════
def get_service_json_path():
    base = sys._MEIPASS if getattr(sys,'frozen',False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base,'voice.json')

def init_firebase_from_embedded(database_url=None):
    path=get_service_json_path()
    if not os.path.exists(path): raise FileNotFoundError(f'Firebase file not found: {path}')
    cred=credentials.Certificate(path)
    firebase_admin.initialize_app(cred,{'databaseURL':database_url or 'https://tia-ai-96c7c-default-rtdb.firebaseio.com/'})

ACTIVATION_FILE=os.path.join(os.environ.get('APPDATA',os.path.expanduser('~')),'TIA','activation.json')

def save_activation_data(data:dict):
    try:
        os.makedirs(os.path.dirname(ACTIVATION_FILE),exist_ok=True)
        ex=load_activation_data(); ex.update(data)
        with open(ACTIVATION_FILE,'w') as f: json.dump(ex,f)
    except Exception as e: print(f'Save activation error: {e}')

def load_activation_data()->dict:
    try:
        if os.path.exists(ACTIVATION_FILE):
            with open(ACTIVATION_FILE,'r') as f: return json.load(f)
    except Exception: pass
    return {}

def clear_activation_data():
    try:
        if os.path.exists(ACTIVATION_FILE): os.remove(ACTIVATION_FILE)
    except Exception: pass

def set_env_variable(key,value):
    try: os.environ[key]=value; save_activation_data({key:value})
    except Exception as e: print(f'set_env error: {e}')

def get_bool(v):
    if isinstance(v,bool): return v
    if isinstance(v,str): return v.strip().lower() in ['true','1','yes']
    return False


class TIAActivationDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.user_name=None; self.access_key=None
        self.setWindowTitle('TIA AI — Activation'); self.setFixedSize(480,580)
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag=None; self._build_ui()

    def _build_ui(self):
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        card=QWidget(); card.setObjectName('card')
        card.setStyleSheet('QWidget#card{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0a0a1a,stop:0.5 #0d1333,stop:1 #0a0a1a);border-radius:24px;border:1.5px solid rgba(0,140,255,0.4);}')
        cl=QVBoxLayout(card); cl.setContentsMargins(40,40,40,40); cl.setSpacing(20)
        logo=QLabel('TIA'); logo.setAlignment(Qt.AlignCenter); logo.setFixedSize(100,100)
        logo.setStyleSheet('QLabel{background:qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 #0066ff,stop:0.6 #0033aa,stop:1 #001166);border-radius:50px;color:white;font-size:22px;font-weight:900;font-family:"Segoe UI";border:2px solid rgba(0,160,255,0.8);}')
        lc=QWidget(); ll=QHBoxLayout(lc); ll.addStretch(); ll.addWidget(logo); ll.addStretch(); cl.addWidget(lc)
        for txt,sty in [('Welcome to TIA AI','color:white;font-size:22px;font-weight:700;font-family:"Segoe UI";'),
                        ('Enter your details to activate','color:rgba(150,180,255,0.8);font-size:13px;font-family:"Segoe UI";')]:
            l=QLabel(txt); l.setAlignment(Qt.AlignCenter); l.setStyleSheet(sty); cl.addWidget(l)
        div=QWidget(); div.setFixedHeight(1); div.setStyleSheet('background:rgba(0,140,255,0.3);'); cl.addWidget(div)
        for lt,attr,ph,ls in [('Your Name','name_input','Enter your name...',''),
                               ('Activation Key','key_input','XXXX-XXXX-XXXX-XXXX','letter-spacing:2px;')]:
            lb=QLabel(lt); lb.setStyleSheet('color:rgba(150,180,255,0.9);font-size:12px;font-family:"Segoe UI";font-weight:600;'); cl.addWidget(lb)
            f=QLineEdit(); f.setPlaceholderText(ph); f.setFixedHeight(48)
            f.setStyleSheet(f'QLineEdit{{background:rgba(0,80,200,0.15);border:1.5px solid rgba(0,140,255,0.4);border-radius:12px;color:white;font-size:14px;font-family:"Segoe UI";padding:0 16px;{ls}}}QLineEdit:focus{{border:1.5px solid rgba(0,180,255,0.9);background:rgba(0,80,200,0.25);}}')
            setattr(self,attr,f); cl.addWidget(f)
        self.err=QLabel(''); self.err.setAlignment(Qt.AlignCenter)
        self.err.setStyleSheet('color:#ff4444;font-size:12px;font-family:"Segoe UI";'); cl.addWidget(self.err)
        self.btn=QPushButton('✨  Activate TIA'); self.btn.setFixedHeight(52); self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setStyleSheet('QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0055ff,stop:1 #0099ff);border:none;border-radius:14px;color:white;font-size:15px;font-weight:700;font-family:"Segoe UI";}QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0066ff,stop:1 #00aaff);}')
        self.btn.clicked.connect(self._activate); cl.addWidget(self.btn)
        cb=QPushButton('Exit'); cb.setFixedHeight(40); cb.setCursor(Qt.PointingHandCursor)
        cb.setStyleSheet('QPushButton{background:transparent;border:1px solid rgba(255,80,80,0.4);border-radius:10px;color:rgba(255,100,100,0.8);font-size:13px;font-family:"Segoe UI";}QPushButton:hover{background:rgba(255,60,60,0.15);color:#ff4444;}')
        cb.clicked.connect(lambda: sys.exit(0)); cl.addWidget(cb)
        ft=QLabel('TIA AI — Created by Soham Sir'); ft.setAlignment(Qt.AlignCenter)
        ft.setStyleSheet('color:rgba(100,130,200,0.5);font-size:11px;font-family:"Segoe UI";'); cl.addWidget(ft)
        layout.addWidget(card)

    def _activate(self):
        n=self.name_input.text().strip(); k=self.key_input.text().strip()
        if not n: self.err.setText('⚠️ Please enter your name'); self.name_input.setFocus(); return
        if not k: self.err.setText('⚠️ Please enter your activation key'); self.key_input.setFocus(); return
        self.btn.setText('Verifying...'); self.btn.setEnabled(False); self.err.setText('')
        QApplication.processEvents()
        self.user_name=n; self.access_key=k; self.accept()

    def show_error(self,msg):
        self.err.setText(f'❌ {msg}'); self.btn.setText('✨  Activate TIA'); self.btn.setEnabled(True)

    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton: self._drag=e.globalPos()-self.frameGeometry().topLeft()
    def mouseMoveEvent(self,e):
        if e.buttons()==Qt.LeftButton and self._drag: self.move(e.globalPos()-self._drag)
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        for i in range(8): p.setPen(Qt.NoPen); p.setBrush(QColor(0,100,255,30)); p.drawRoundedRect(self.rect().adjusted(-i,-i,i,i),28+i,28+i)


def prompt_user_name():
    while True:
        n,ok=QInputDialog.getText(None,'User Setup','Enter your name:')
        if not ok:
            if QMessageBox.question(None,'Confirm',"Use 'User'?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes: return 'User'
        elif n.strip(): return n.strip()
        else: QMessageBox.warning(None,'Invalid','Name cannot be empty.')

def prompt_lan():
    while True:
        n,ok=QInputDialog.getText(None,'Language Setup','Enter your language:')
        if not ok:
            if QMessageBox.question(None,'Confirm',"Use 'Hindi'?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes: return 'Hindi'
        elif n.strip(): return n.strip()
        else: QMessageBox.warning(None,'Invalid','Cannot be empty.')

def prompt_agent_name():
    while True:
        n,ok=QInputDialog.getText(None,'Assistant Name','Enter assistant name:')
        if not ok:
            if QMessageBox.question(None,'Confirm',"Use 'TIA'?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes: return 'TIA'
        elif n.strip(): return n.strip()
        else: QMessageBox.warning(None,'Invalid','Cannot be empty.')

def ensure_user_name():
    cur=os.getenv('USER_NAME','').strip()
    if cur: return cur
    un=prompt_user_name(); ln=prompt_lan(); an=prompt_agent_name()
    for k,v in [('USER_NAME',un),('LAN',ln),('AGENT_NAME',an)]:
        set_env_variable(k,v); os.environ[k]=v
    print(f'✅ Profile set: {un}, {ln}')
    return un


BASE_SECRET    = 'u3WwL1EuB0BfaNIV2pbGsrOx8mgOms48Me56BUW60tD6wcUkwfrhHjIR0Aq9EhCT0l5jU6J8pePgcPX14Upn85hIr7'
PREMIUM_SECRET = 'VpVwo5yMnwh1IDwTaoHzEZ9xGdRCdaMZyqiTecfazjWEyFXoZTRFnHNrDWV7BqFcjGJIsxcF7gMHqL73'
ELITE_SECRET   = 'uXqG3kOo6TS1AjkT8lTHufqkotWk397AjLS1xmWuXilBKN679AswENJnZRikxZQjIj57DYvXA3J3NGXAjhJ3E'
VARIANT_SECRET_MAP={'base':BASE_SECRET,'premium':PREMIUM_SECRET,'elite':ELITE_SECRET}
VARIANT_NAMES={'base':'Base','premium':'Premium','elite':'Elite'}

def detect_variant_and_ref(key):
    for v in ['base','premium','elite']:
        ref=db.reference(f'tia{v}/{key}'); rec=ref.get()
        if rec is not None: return (v,ref,rec)
    return (None,None,None)

def activation_gate():
    ak=os.getenv('ACCESS_KEY'); ia=os.getenv('IS_ACTIVATED','').strip().lower()=='true'
    try: ac=int(os.getenv('ACTIVATION_COUNT','0').strip() or '0')
    except: ac=0
    if ia and ak and ac>=1: return True
    while True:
        dlg=TIAActivationDialog(); scr=QApplication.desktop().screenGeometry()
        dlg.move((scr.width()-dlg.width())//2,(scr.height()-dlg.height())//2)
        if dlg.exec_()!=QDialog.Accepted: sys.exit(0)
        un=dlg.user_name; ak=dlg.access_key
        variant,ref,rec=detect_variant_and_ref(ak)
        if not variant:
            e=TIAActivationDialog(); e.name_input.setText(un); e.key_input.setText(ak)
            e.err.setText('❌ Invalid key.'); e.move((scr.width()-e.width())//2,(scr.height()-e.height())//2); e.exec_(); continue
        if get_bool(rec.get('isUsed')):
            e=TIAActivationDialog(); e.name_input.setText(un)
            e.err.setText('❌ Key already used.'); e.move((scr.width()-e.width())//2,(scr.height()-e.height())//2); e.exec_(); continue
        try: ref.update({'isUsed':True})
        except Exception as ex: QMessageBox.critical(None,'Error',f'Server error: {ex}'); return False
        for k,v in [('ACCESS_KEY',ak),('IS_ACTIVATED','true'),('ACTIVATION_COUNT','1'),
                    ('TIA_VARIANT',variant),('SYSTEM_CONST_32',VARIANT_SECRET_MAP[variant]),('USER_NAME',un)]:
            set_env_variable(k,v); os.environ[k]=v
        return True

def safe_activation_gate():
    try:
        if activation_gate(): return (True,'activated')
        return (False,'failed')
    except Exception as e:
        print('Activation error:',e); print(traceback.format_exc())
        QMessageBox.warning(None,'Warning','Firebase error. Fallback mode.')
        return (False,'fallback')


# ═══════════════════════════════════════════════════════════════
#  TIA STARTUP POPUP  — "Hello! I'm waking up..."
# ═══════════════════════════════════════════════════════════════
class TIAStartupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('TIA AI')
        self.setFixedSize(520, 300)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName('tia_card')
        card.setStyleSheet("""
            QWidget#tia_card {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #030d1a, stop:0.5 #051428, stop:1 #030d1a);
                border-radius: 18px;
                border: 1.5px solid rgba(0, 200, 255, 0.5);
            }
        """)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 24, 28, 24)
        cl.setSpacing(14)

        # Header row: avatar + title
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(14)

        avatar = QLabel('TIA')
        avatar.setFixedSize(56, 56)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("""
            QLabel {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,
                    stop:0 #1a6aff, stop:0.6 #0a3aaa, stop:1 #05154a);
                border-radius: 28px;
                color: white;
                font-size: 14px;
                font-weight: 900;
                font-family: Arial;
                border: 2px solid rgba(0, 200, 255, 0.9);
            }
        """)
        hl.addWidget(avatar)

        title = QLabel('TIA AI')
        title.setStyleSheet("""
            color: white;
            font-size: 26px;
            font-weight: 800;
            font-family: Arial;
            letter-spacing: 2px;
        """)
        hl.addWidget(title)
        hl.addStretch()

        close_btn = QPushButton('✕')
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: rgba(255,255,255,0.5);
                font-size: 14px;
            }
            QPushButton:hover { color: white; }
        """)
        close_btn.clicked.connect(lambda: __import__('sys').exit(0))
        hl.addWidget(close_btn)
        cl.addWidget(header)

        # Divider
        div = QWidget(); div.setFixedHeight(1)
        div.setStyleSheet('background: rgba(0,200,255,0.25);')
        cl.addWidget(div)

        # Message
        msg = QLabel("Hello! I'm waking up...")
        msg.setStyleSheet("""
            color: white;
            font-size: 20px;
            font-weight: 600;
            font-family: Arial;
        """)
        cl.addWidget(msg)

        sub = QLabel('To function at my best, I need an internet connection.\nPlease make sure you\'re connected.')
        sub.setWordWrap(True)
        sub.setStyleSheet("""
            color: rgba(180,220,255,0.85);
            font-size: 13px;
            font-family: Arial;
            line-height: 1.6;
        """)
        cl.addWidget(sub)
        cl.addStretch()

        # Start button
        btn = QPushButton('Start TIA')
        btn.setFixedHeight(46)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1.5px solid rgba(0,200,255,0.7);
                border-radius: 10px;
                color: rgba(0,220,255,1.0);
                font-size: 15px;
                font-weight: 600;
                font-family: Arial;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: rgba(0,200,255,0.12);
                border: 1.5px solid rgba(0,220,255,1.0);
                color: white;
            }
        """)
        btn.clicked.connect(self.accept)
        cl.addWidget(btn)

        layout.addWidget(card)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag:
            self.move(e.globalPos() - self._drag)
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Outer glow rings
        for i in range(6):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 100, 200, max(0, 18 - i*3)))
            p.drawRoundedRect(self.rect().adjusted(-i, -i, i, i), 20+i, 20+i)


# ═══════════════════════════════════════════════════════════════
#  TIA INTERNET CHECK DIALOG  — "Connection Check"
# ═══════════════════════════════════════════════════════════════
class WaitForInternetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('TIA – Connection Check')
        self.setFixedSize(520, 340)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag = None
        self._progress = 0
        self._connected = False
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(40)
        self._build_ui()
        self.sec = 10
        QTimer.singleShot(800, self.check)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName('conn_card')
        card.setStyleSheet("""
            QWidget#conn_card {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #030d1a, stop:0.5 #051428, stop:1 #030d1a);
                border-radius: 18px;
                border: 1.5px solid rgba(0, 200, 255, 0.5);
            }
        """)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 24, 28, 24)
        cl.setSpacing(14)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(14)

        avatar = QLabel('TIA')
        avatar.setFixedSize(56, 56)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("""
            QLabel {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,
                    stop:0 #1a6aff, stop:0.6 #0a3aaa, stop:1 #05154a);
                border-radius: 28px;
                color: white;
                font-size: 14px;
                font-weight: 900;
                font-family: Arial;
                border: 2px solid rgba(0, 200, 255, 0.9);
            }
        """)
        hl.addWidget(avatar)

        title = QLabel('TIA – Connection Check')
        title.setStyleSheet("""
            color: white;
            font-size: 20px;
            font-weight: 700;
            font-family: Arial;
            letter-spacing: 1px;
        """)
        hl.addWidget(title)
        hl.addStretch()

        close_btn = QPushButton('✕')
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton { background:transparent; border:none; color:rgba(255,255,255,0.5); font-size:14px; }
            QPushButton:hover { color:white; }
        """)
        close_btn.clicked.connect(self.reject)
        hl.addWidget(close_btn)
        cl.addWidget(header)

        div = QWidget(); div.setFixedHeight(1)
        div.setStyleSheet('background: rgba(0,200,255,0.25);')
        cl.addWidget(div)

        # Status message
        self.msg = QLabel('Checking my connection to the world...')
        self.msg.setStyleSheet("""
            color: white;
            font-size: 17px;
            font-weight: 600;
            font-family: Arial;
        """)
        cl.addWidget(self.msg)

        # Sub label
        self.sub = QLabel('Establishing internet link')
        self.sub.setStyleSheet("""
            color: rgba(180,220,255,0.8);
            font-size: 12px;
            font-family: Arial;
        """)
        cl.addWidget(self.sub)

        # Custom progress bar
        self.pb = QProgressBar()
        self.pb.setRange(0, 100)
        self.pb.setValue(0)
        self.pb.setFixedHeight(10)
        self.pb.setTextVisible(False)
        self.pb.setStyleSheet("""
            QProgressBar {
                background: rgba(0,30,60,0.8);
                border-radius: 5px;
                border: 1px solid rgba(0,200,255,0.2);
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #0088cc, stop:1 #00ddff);
                border-radius: 5px;
            }
        """)
        cl.addWidget(self.pb)

        # Status sub text
        self.status_lbl = QLabel('Almost ready to begin.')
        self.status_lbl.setStyleSheet("""
            color: rgba(180,220,255,0.7);
            font-size: 12px;
            font-family: Arial;
        """)
        cl.addWidget(self.status_lbl)
        cl.addStretch()

        # Cancel button
        btn = QPushButton('Cancel Startup')
        btn.setFixedHeight(46)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1.5px solid rgba(0,200,255,0.5);
                border-radius: 10px;
                color: rgba(0,200,255,0.9);
                font-size: 14px;
                font-weight: 600;
                font-family: Arial;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: rgba(0,200,255,0.1);
                border-color: rgba(0,220,255,1.0);
                color: white;
            }
        """)
        btn.clicked.connect(self.reject)
        cl.addWidget(btn)

        layout.addWidget(card)

    def _animate(self):
        """Animate progress bar smoothly."""
        if self._connected:
            self._progress = min(100, self._progress + 3)
        else:
            # Oscillate between 15-55 while checking
            import math
            t = self._anim_timer.remainingTime()
            val = 35 + int(20 * math.sin(time.time() * 2))
            self._progress = max(10, min(55, val))
        self.pb.setValue(self._progress)

    def check(self):
        if self._ok():
            self._connected = True
            self.msg.setText('✅ Connected!')
            self.sub.setText('Internet connection established')
            self.status_lbl.setText('TIA is ready to begin.')
            QTimer.singleShot(1200, self.accept)
        else:
            self.sec = 10
            self.msg.setText('Checking my connection to the world...')
            self.sub.setText('❌ No internet. Retrying...')
            self._ct = QTimer()
            self._ct.timeout.connect(self._cd)
            self._ct.start(1000)

    def _cd(self):
        self.sec -= 1
        self.status_lbl.setText(f'Next check in: {self.sec}s')
        if self.sec <= 0: self._ct.stop(); self.check()

    def _ok(self):
        try: socket.create_connection(('8.8.8.8', 53), timeout=5); return True
        except:
            try: socket.create_connection(('google.com', 80), timeout=5); return True
            except: return False

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag:
            self.move(e.globalPos() - self._drag)
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for i in range(6):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 100, 200, max(0, 18 - i*3)))
            p.drawRoundedRect(self.rect().adjusted(-i, -i, i, i), 20+i, 20+i)


def wait_for_internet():
    return WaitForInternetDialog().exec_() == QDialog.Accepted


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    global app
    app=QApplication(sys.argv)
    app.setApplicationName('TIA AI'); app.setApplicationVersion('2.0')
    app.setQuitOnLastWindowClosed(False)

    TIA_SECRETS=[BASE_SECRET,PREMIUM_SECRET,ELITE_SECRET]
    saved=load_activation_data()
    if saved:
        for k,v in saved.items(): os.environ[k]=str(v)
        print('✅ Activation loaded from file')
    cs=os.environ.get('SYSTEM_CONST_32','')
    if cs and cs not in TIA_SECRETS:
        for k in ['ACCESS_KEY','IS_ACTIVATED','ACTIVATION_COUNT','SYSTEM_CONST_32','TIA_VARIANT']:
            os.environ.pop(k,None)
        clear_activation_data(); print('🧹 Old data cleared')

    print('🚀 TIA AI PREMIUM EDITION STARTING')
    # Show styled TIA startup popup
    _startup = TIAStartupDialog()
    scr = QApplication.desktop().screenGeometry()
    _startup.move((scr.width()-_startup.width())//2, (scr.height()-_startup.height())//2)
    if _startup.exec_() != QDialog.Accepted:
        return 0

    if not wait_for_internet():
        QMessageBox.critical(None,'Error','Internet required.'); return 1

    try:
        init_firebase_from_embedded()
        ok,status=safe_activation_gate()
        if not ok:
            if status=='failed': QMessageBox.critical(None,'Error','Activation failed.'); return 1
            QMessageBox.warning(None,'Fallback','Running in fallback mode.')
    except Exception as e:
        QMessageBox.critical(None,'Firebase Error',str(e)); return 1

    user_name=ensure_user_name()
    print(f'✅ User: {user_name}')

    main_window = ModernFloatingWindow()
    boot = TIABootScreen()
    boot.show()

    def on_boot_done():
        main_window.show()
        main_window.raise_()
        print(f'👤 Welcome {user_name}! Starting agent...')
        main_window.start_agent()
        ka=QTimer()
        ka.timeout.connect(lambda: (main_window.show(),main_window.raise_()) if not main_window.isVisible() else None)
        ka.start(5000)

    boot.set_on_done(on_boot_done)

    result=app.exec_()
    print(f'🔚 Exited: {result}')
    return result


if __name__=='__main__':
    os._exit(main())