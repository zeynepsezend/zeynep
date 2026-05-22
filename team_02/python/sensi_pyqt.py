"""
sensi_pyqt.py — Sensi desktop app (PyQt5 + QWebEngineView)

Run:     python sensi_pyqt.py
Install: pip install PyQt5 PyQtWebEngine

Architecture:
  QMainWindow
  └── QWebEngineView          ← full-window browser frame
       └── ui/index.html      ← all Sensi screens (HTML/CSS/JS)
            └── QWebChannel   ← Python ↔ JS bridge (SensiBridge)

The UI lives entirely in HTML/CSS/JS.
Python exposes the LangGraph backend through SensiBridge slots.
"""

import sys
import json
import re
import os
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal, QThread, QUrl
from PyQt5.QtGui import QColor

# Add the python/ directory to path so _runtime and graph are importable
sys.path.insert(0, str(Path(__file__).parent))

from _runtime.bootstrap import bootstrap
from graph import run_agent

# ── Paths ─────────────────────────────────────────────────────────────────────
_PERSONA_PATH = Path(__file__).resolve().parent.parent / "persona.json"
_UI_PATH      = Path(__file__).resolve().parent / "ui" / "index.html"


# ═══════════════════════════════════════════════════════════════════════════════
# Worker threads  (keep the Qt main thread free — never block it with LLM calls)
# ═══════════════════════════════════════════════════════════════════════════════

class AgentWorker(QThread):
    """Runs one LangGraph turn off the main thread."""
    finished = pyqtSignal(str)   # JSON: {ok, message, session}
    error    = pyqtSignal(str)

    def __init__(self, text: str, ctx, session: dict):
        super().__init__()
        self.text    = text
        self.ctx     = ctx
        self.session = session

    def run(self):
        try:
            response, new_session = run_agent(self.text, self.ctx, self.session)
            self.finished.emit(json.dumps({
                "ok":      True,
                "message": response,
                "session": new_session,
            }))
        except Exception as exc:
            self.error.emit(json.dumps({"ok": False, "error": str(exc)}))


class InspireWorker(QThread):
    """VLM analysis + Unsplash query generation + image fetch — off the main thread."""
    finished = pyqtSignal(str)   # JSON: {ok, round, urls, descs, analysis}
    progress = pyqtSignal(str)   # status string sent to the loading overlay

    def __init__(self, text: str, b64s: list, ctx,
                 existing_analysis: str, round_num: int, refine_desc: str = ""):
        super().__init__()
        self.text              = text
        self.b64s              = b64s
        self.ctx               = ctx
        self.existing_analysis = existing_analysis
        self.round_num         = round_num
        self.refine_desc       = refine_desc

    def run(self):
        try:
            llm = self.ctx.llm_simple

            # Step 1 — VLM (first round only; subsequent rounds reuse analysis)
            self.progress.emit("reading your aesthetic...")
            analysis = (
                self.existing_analysis
                or _vlm_analyze(llm, self.b64s, self.text)
            )

            # Step 2 — Unsplash query generation
            self.progress.emit("building search queries...")
            n_map = {1: (4, 3), 2: (3, 3), 3: (2, 3)}
            n_queries, per_q = n_map.get(self.round_num, (3, 3))
            queries = _gen_queries(
                llm, analysis,
                prev_desc=self.refine_desc,
                n=n_queries,
            )

            # Step 3 — Fetch images
            self.progress.emit("gathering images...")
            urls, descs = _fetch_unsplash(queries, per_query=per_q)

            self.finished.emit(json.dumps({
                "ok":       True,
                "round":    self.round_num,
                "urls":     urls,
                "descs":    descs,
                "analysis": analysis,
            }))
        except Exception as exc:
            self.finished.emit(json.dumps({"ok": False, "error": str(exc)}))


# ═══════════════════════════════════════════════════════════════════════════════
# Inspire helpers — VLM + Unsplash pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def _vlm_analyze(llm, images_b64: list, text_desc: str) -> str:
    from langchain_core.messages import HumanMessage
    SYSTEM = (
        "You are a spatial aesthetic analyst. Extract a rich sensory and visual "
        "profile from the provided reference images and/or description.\n\n"
        "Capture:\n"
        "  • Color palette — dominant hues, temperature (warm/cool), saturation\n"
        "  • Light quality — source (natural/artificial), quality (soft/harsh/diffuse), tone\n"
        "  • Materials & textures — wood, stone, concrete, fabric, metal, plaster, plant\n"
        "  • Spatial mood — intimate/open, minimal/layered, calm/dynamic, raw/refined\n"
        "  • Atmosphere — time of day feel, level of cosiness vs grandeur\n\n"
        "Write a specific, grounded aesthetic profile in 120–150 words. "
        "No lists. No headers. Just a flowing description."
    )
    if images_b64:
        content = [{"type": "text", "text": f"{SYSTEM}\n\nUser description: {text_desc}"}]
        for b64 in images_b64[:4]:
            content.append({"type": "image_url",
                             "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        try:
            return llm.invoke([HumanMessage(content=content)]).content.strip()
        except Exception:
            pass  # fall through to text-only
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user",   "content": text_desc or "minimalist interior, warm and natural"},
    ]
    try:
        return llm.invoke(messages).content.strip()
    except Exception:
        return f"Aesthetic preference: {text_desc}"


def _gen_queries(llm, analysis: str, prev_desc: str = "", n: int = 4) -> list:
    from langchain_core.messages import HumanMessage
    extra  = f"\n\nThe user particularly liked: {prev_desc}" if prev_desc else ""
    prompt = (
        f"Aesthetic analysis:\n{analysis}{extra}\n\n"
        f"Generate {n} specific Unsplash search queries to find interior architectural spaces "
        f"matching this aesthetic. Include materials, light quality, and mood words.\n"
        f"RULES: Every query MUST describe an interior room, residential space, or architectural scene. "
        f"No people, no landscapes, no food, no fashion, no abstract imagery.\n"
        f"Each query = 3–5 words.\nReturn ONLY a JSON array: [\"q1\", \"q2\", ...]"
    )
    defaults = [
        "minimal interior warm natural light",
        "calm architectural space texture material",
        "serene residential room daylight",
        "intimate atmospheric interior comfort",
    ]
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        m = re.search(r"\[.*?\]", resp.content, re.DOTALL)
        if m:
            parsed = json.loads(m.group())
            if isinstance(parsed, list) and parsed:
                return [str(q) for q in parsed[:n]]
    except Exception:
        pass
    return defaults[:n]


def _fetch_unsplash(queries: list, per_query: int = 3) -> tuple:
    import httpx
    key = os.getenv("UNSPLASH_ACCESS_KEY", "")
    if not key:
        return [], []
    urls, descs = [], []
    for q in queries:
        try:
            resp = httpx.get(
                "https://api.unsplash.com/search/photos",
                params={"query": q, "per_page": per_query, "orientation": "landscape"},
                headers={"Authorization": f"Client-ID {key}"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                for r in resp.json().get("results", []):
                    urls.append(r["urls"]["small"])
                    descs.append(r.get("alt_description") or q)
        except Exception:
            pass
    return urls, descs


# ═══════════════════════════════════════════════════════════════════════════════
# Bridge  — Python object exposed to JavaScript via QWebChannel
# ═══════════════════════════════════════════════════════════════════════════════

class SensiBridge(QObject):
    """
    Every public @pyqtSlot method is callable from JS as:
        bridge.methodName(arg1, arg2)
    Python calls JS by:
        self._js("functionName", arg1, arg2)
    """

    def __init__(self, view: QWebEngineView, ctx):
        super().__init__()
        self._view    = view
        self._ctx     = ctx
        self._session: dict = {}
        self._inspire: dict = {
            "analysis":    "",
            "text":        "",
            "b64s":        [],
            "r1_picks":    [],
            "r2_picks":    [],
            "final_picks": [],
        }
        self._worker = None   # reference kept to prevent GC

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _js(self, fn: str, *args):
        """Call window.<fn>(...args) in the browser, args JSON-serialised."""
        serialized = ", ".join(json.dumps(a) for a in args)
        self._view.page().runJavaScript(f"window.{fn}({serialized})")

    def _read_persona(self) -> dict | None:
        if _PERSONA_PATH.exists():
            try:
                return json.loads(_PERSONA_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def _screen_from_session(self, sess: dict) -> str:
        if not sess.get("quiz_complete"):
            return "quiz"
        if not sess.get("inspire_complete"):
            return "inspire"
        return "chat"

    # ── App lifecycle ─────────────────────────────────────────────────────────

    @pyqtSlot()
    def initApp(self):
        """
        Called by JS once the page is fully loaded.
        Returns initial state so JS can route to the right screen.
        """
        persona = self._read_persona()
        if persona:
            self._session = {
                "onboarding_complete": True,
                "greeted":             True,
                "quiz_complete":       True,
                "inspire_complete":    True,
                "persona_profile":     persona,
                "user_type":           persona.get("role", "client"),
            }
            name = persona.get("name", "")
            msg  = (
                f"Welcome back{', ' + name if name else ''}! "
                "Your comfort profile is loaded. "
                "Tell me which layout you'd like to explore."
            )
            self._js("receiveInit", {
                "screen":     "chat",
                "message":    msg,
                "has_persona": True,
                "persona":    persona,
            })
        else:
            # Run the silent greeting turn (empty input → greet node fires)
            self._worker = AgentWorker("", self._ctx, {})
            self._worker.finished.connect(self._on_init_done)
            self._worker.error.connect(
                lambda e: self._js("receiveError", json.loads(e).get("error", e))
            )
            self._worker.start()

    def _on_init_done(self, result_json: str):
        result = json.loads(result_json)
        if result.get("ok"):
            self._session = result["session"]
            self._js("receiveInit", {
                "screen":      "quiz",
                "message":     result["message"],
                "has_persona": False,
                "quiz_step":   self._session.get("quiz_step", 0),
            })
        else:
            self._js("receiveError", result.get("error", "init failed"))

    @pyqtSlot()
    def resetPersona(self):
        """Delete persona.json and restart full onboarding."""
        if _PERSONA_PATH.exists():
            _PERSONA_PATH.unlink()
        self._session = {}
        self._inspire = {
            "analysis": "", "text": "", "b64s": [],
            "r1_picks": [], "r2_picks": [], "final_picks": [],
        }
        self.initApp()

    # ── Quiz + Chat turns ─────────────────────────────────────────────────────

    @pyqtSlot(str)
    def sendMessage(self, text: str):
        """
        Run one agent turn.  Works for both quiz and chat contexts —
        the graph routes internally based on session state.
        """
        self._worker = AgentWorker(text, self._ctx, self._session)
        self._worker.finished.connect(self._on_agent_response)
        self._worker.error.connect(
            lambda e: self._js("receiveError", json.loads(e).get("error", e))
        )
        self._worker.start()

    def _on_agent_response(self, result_json: str):
        result = json.loads(result_json)
        if not result.get("ok"):
            self._js("receiveError", result.get("error", "agent error"))
            return

        self._session = result["session"]
        sess          = self._session
        screen        = self._screen_from_session(sess)

        self._js("receiveResponse", {
            "ok":                   True,
            "screen":               screen,
            "message":              result["message"],
            "quiz_step":            sess.get("quiz_step", 0),
            "quiz_complete":        sess.get("quiz_complete", False),
            "inspire_complete":     sess.get("inspire_complete", False),
            "onboarding_complete":  sess.get("onboarding_complete", False),
        })

    # ── File picker (native OS dialog) ───────────────────────────────────────

    @pyqtSlot()
    def openFilePicker(self):
        """Open a native file dialog; base64-encode selected images → receiveFiles."""
        import base64
        from PyQt5.QtWidgets import QFileDialog
        files, _ = QFileDialog.getOpenFileNames(
            None, "Select reference images", "",
            "Images (*.jpg *.jpeg *.png *.webp)"
        )
        if not files:
            return
        b64s = []
        for f in files[:5]:
            try:
                b64s.append(base64.b64encode(Path(f).read_bytes()).decode())
            except Exception:
                pass
        self._js("receiveFiles", b64s)

    # ── Inspire pipeline ──────────────────────────────────────────────────────

    @pyqtSlot(str, str, int)
    def prepareInspire(self, text: str, b64s_json: str, round_num: int):
        """
        Kick off VLM analysis + Unsplash fetch for round <round_num>.
        b64s_json: JSON array of base64-encoded image strings (may be "[]").
        Calls window.receiveImages({round, urls, descs}) when done.
        """
        b64s = json.loads(b64s_json) if b64s_json else []
        self._inspire["text"] = text
        self._inspire["b64s"] = b64s

        self._worker = InspireWorker(
            text, b64s, self._ctx,
            self._inspire["analysis"],
            round_num,
        )
        self._worker.progress.connect(
            lambda msg: self._js("receiveProgress", msg)
        )
        self._worker.finished.connect(self._on_inspire_ready)
        self._worker.start()

    @pyqtSlot(str, int)
    def refineInspire(self, refine_desc: str, round_num: int):
        """Fetch next image round with a refinement cue."""
        self._worker = InspireWorker(
            self._inspire["text"],
            self._inspire["b64s"],
            self._ctx,
            self._inspire["analysis"],
            round_num,
            refine_desc,
        )
        self._worker.progress.connect(
            lambda msg: self._js("receiveProgress", msg)
        )
        self._worker.finished.connect(self._on_inspire_ready)
        self._worker.start()

    def _on_inspire_ready(self, result_json: str):
        result = json.loads(result_json)
        if result.get("ok"):
            self._inspire["analysis"] = result.get("analysis", self._inspire["analysis"])
            self._js("receiveImages", {
                "round": result["round"],
                "urls":  result["urls"],
                "descs": result["descs"],
            })
        else:
            self._js("receiveError", result.get("error", "inspire fetch failed"))

    @pyqtSlot(int, str)
    def saveInspirePicks(self, round_num: int, urls_json: str):
        """Store the user's selected image URLs for a given round."""
        urls = json.loads(urls_json)
        key  = {1: "r1_picks", 2: "r2_picks", 3: "final_picks"}.get(round_num, "final_picks")
        self._inspire[key] = urls

    @pyqtSlot()
    def buildMoodboard(self):
        """
        Finalise the inspire phase:
        1. Inject image data into session state
        2. Send the aesthetic description to the graph (triggers persona_compiler)
        3. Return persona data via window.receivePersona(...)
        """
        all_picks: list = list(dict.fromkeys(
            self._inspire["r1_picks"] +
            self._inspire["r2_picks"] +
            self._inspire["final_picks"]
        ))

        # Mirror what app.py does before calling run_agent
        self._session["inspire_image_analysis"] = self._inspire["analysis"]
        self._session["inspire_moodboard_urls"]  = all_picks
        self._session["inspire_prompted"]        = True  # UI handled the aesthetic question; skip inspire sub-step A

        context = (
            f"{self._inspire['text']}\n\n"
            f"[Moodboard context: user selected {len(all_picks)} reference image(s) "
            f"across aesthetic refinement rounds.]"
        )

        self._worker = AgentWorker(context, self._ctx, self._session)
        self._worker.finished.connect(lambda r: self._on_moodboard_done(r, all_picks))
        self._worker.error.connect(
            lambda e: self._js("receiveError", json.loads(e).get("error", e))
        )
        self._worker.start()

    def _on_moodboard_done(self, result_json: str, all_picks: list):
        result = json.loads(result_json)
        if result.get("ok"):
            self._session = result["session"]
            persona       = self._session.get("persona_profile", {})
            self._js("receivePersona", {
                "persona":       persona,
                "moodboard_urls": all_picks[:6],
                "message":       result["message"],
            })
        else:
            self._js("receiveError", result.get("error", "moodboard failed"))


# ═══════════════════════════════════════════════════════════════════════════════
# Main window
# ═══════════════════════════════════════════════════════════════════════════════

class SensiWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.setWindowTitle("sensi")
        self.setMinimumSize(480, 600)
        self.resize(960, 1000)
        self.setStyleSheet("background:#0D0D0D;")

        # Web view
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)

        # Settings  (PyQt5 uses flat enum — no WebAttribute. prefix)
        settings = self.view.settings()
        settings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls, True
        )
        settings.setAttribute(
            QWebEngineSettings.JavascriptEnabled, True
        )
        settings.setAttribute(
            QWebEngineSettings.LocalStorageEnabled, True
        )

        # Dark background while the page loads (no white flash)
        self.view.page().setBackgroundColor(QColor("#0D0D0D"))

        # Bridge
        self.channel = QWebChannel(self.view.page())
        self.bridge  = SensiBridge(self.view, ctx)
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        # Load UI
        self.view.load(QUrl.fromLocalFile(str(_UI_PATH)))


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("[sensi] Bootstrapping backend…")
    ctx = bootstrap()
    print("[sensi] Backend ready — launching UI.")

    app = QApplication(sys.argv)
    app.setApplicationName("Sensi")
    app.setOrganizationName("AIA26 Team 02")

    window = SensiWindow(ctx)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
