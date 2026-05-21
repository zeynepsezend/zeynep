"""
app.py — Sensi GUI  (v3 — full inspire moodboard pipeline)
Dark, editorial, minimalist.  Three screens: quiz → inspire → analysis.

Run from the python/ directory:
    streamlit run app.py

Requires:
    streamlit >= 1.29   (st.container height= needs 1.29+)
    plotly
    httpx               (already in requirements — used for Unsplash)

Optional .env keys:
    UNSPLASH_ACCESS_KEY   — free at unsplash.com/developers
                            If absent, moodboard uses only uploaded images.
"""
from __future__ import annotations
import sys, json, os, base64, re
from pathlib import Path

import streamlit as st

# ── path: make graph.py and nodes/ importable ─────────────────────────────────
_PYTHON_DIR = Path(__file__).parent.resolve()
_TEAM_DIR   = _PYTHON_DIR.parent
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))

# ── page config  (must be the very first Streamlit call) ─────────────────────
st.set_page_config(
    page_title="Sensi",
    page_icon="●",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── sense color + icon system ─────────────────────────────────────────────────
_SC = {
    "thermal":   "#E8836A",
    "visual":    "#D4B96A",
    "acoustic":  "#9B8FD4",
    "spatial":   "#6AB8C8",
    "olfactory": "#8BB88A",
    "tactile":   "#C4A882",
}
_SI = {
    "thermal":   "△",
    "visual":    "○",
    "acoustic":  "∿",
    "spatial":   "□",
    "olfactory": "≈",
    "tactile":   "∶",
}

def _rgba(hex_col: str, a: float = 0.10) -> str:
    h = hex_col.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"

# ── loading messages ──────────────────────────────────────────────────────────
_LOADING = {
    "quiz":         "noting your answer…",
    "inspire":      "weaving your aesthetic profile…",
    "vlm":          "reading your reference images…",
    "queries":      "translating aesthetics into search…",
    "unsplash":     "gathering candidate images…",
    "round_next":   "refining the search…",
    "load":         "loading the layout…",
    "analyze":      "running sensory analysis…",
    "general":      "thinking…",
}

def _infer_context(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ("layout","201","202","203","load")):
        return "load"
    if any(w in t for w in ("analyz","comfort","score","sense","thermal","visual",
                             "acoustic","spatial","olfactory","tactile","full","detect")):
        return "analyze"
    return "general"

# ── Sensi logo SVG ────────────────────────────────────────────────────────────
_LOGO_SVG = """
<svg width="28" height="28" viewBox="0 0 28 28" fill="none"
     xmlns="http://www.w3.org/2000/svg" style="display:inline-block;vertical-align:middle;">
  <circle cx="14" cy="14" r="11" stroke="#F0EDE8" stroke-width="0.8" opacity="0.20"/>
  <circle cx="14" cy="14" r="6"  stroke="#F0EDE8" stroke-width="0.8" opacity="0.35"/>
  <circle cx="14" cy="14" r="2"  fill="#F0EDE8"   opacity="0.70"/>
</svg>
"""

# ── loading overlay HTML ──────────────────────────────────────────────────────
def _loading_html(msg: str, extra_msgs: list[str] | None = None) -> str:
    """
    Full-screen loading overlay with pulse ring and rotating messages.
    msg         : primary message shown first
    extra_msgs  : additional messages to cycle through (optional)
    """
    all_msgs = [msg] + (extra_msgs or [])
    msgs_js  = str(all_msgs).replace("'", "\\'").replace('"', '\\"')
    return f"""
<div id="sensi-loader" style="position:fixed;top:0;left:0;right:0;bottom:0;
     background:rgba(13,13,13,0.94);z-index:9998;
     display:flex;flex-direction:column;align-items:center;justify-content:center;gap:0;">

  <p style="font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.35em;
            text-transform:uppercase;color:rgba(240,237,232,.15);margin:0 0 48px;">sensi</p>

  <!-- Pulse ring -->
  <div style="position:relative;width:48px;height:48px;margin-bottom:44px;">
    <div style="position:absolute;inset:-10px;border-radius:50%;
                border:1px solid rgba(240,237,232,.05);
                animation:pulse-outer 2.2s ease-in-out infinite;"></div>
    <div style="width:48px;height:48px;border-radius:50%;
                border:1px solid rgba(240,237,232,.15);
                animation:pulse-ring 2.2s ease-in-out infinite;"></div>
    <div style="position:absolute;top:50%;left:50%;width:8px;height:8px;
                border-radius:50%;background:rgba(240,237,232,.6);
                animation:pulse-core 2.2s ease-in-out infinite;"></div>
  </div>

  <!-- Rotating message -->
  <p id="sensi-load-msg"
     style="font-family:'Roboto',sans-serif;font-weight:300;font-size:16px;
            color:rgba(240,237,232,.45);text-align:center;
            margin:0;max-width:320px;line-height:1.6;
            transition:opacity .35s ease;">{msg}</p>
</div>
<script>
(function(){{
  var msgs  = {all_msgs};
  var el    = document.getElementById('sensi-load-msg');
  var idx   = 0;
  if (!el || msgs.length < 2) return;
  setInterval(function(){{
    el.style.opacity = '0';
    setTimeout(function(){{
      idx = (idx + 1) % msgs.length;
      el.textContent = msgs[idx];
      el.style.opacity = '1';
    }}, 350);
  }}, 2400);
}})();
</script>
"""

# ── global CSS ────────────────────────────────────────────────────────────────
st.markdown(r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;1,9..40,300&family=DM+Mono:wght@300&display=swap');

@keyframes breathe {
  0%,100% { background-color:#0D0D0D; }
  50%      { background-color:#101010; }
}
@keyframes fadeUp {
  from { opacity:0; transform:translateY(16px); }
  to   { opacity:1; transform:translateY(0);    }
}

.stApp,
[data-testid="stAppViewContainer"] {
  background-color:#0D0D0D !important;
  animation: breathe 4s ease-in-out infinite;
  font-family:'DM Sans',sans-serif;
}

[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stDecoration"],#MainMenu,footer,header {
  display:none !important;
}
.block-container { padding:0 !important; max-width:100% !important; }

.fade-up { animation:fadeUp .4s ease-out forwards; }

/* inputs */
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
  border:none !important;
  border-bottom:1px solid rgba(240,237,232,.18) !important;
  border-radius:0 !important;
  font-family:'DM Sans',sans-serif !important;
  font-size:15px !important;
  padding:10px 0 !important;
  caret-color:#F0EDE8 !important;
  box-shadow:none !important;
  background:transparent !important;
}
.stTextInput > div > div > input:focus,
.stTextArea  > div > div > textarea:focus {
  border-bottom-color:rgba(240,237,232,.65) !important;
  box-shadow:none !important;
  outline:none !important;
}
.stTextInput > div > div > input::placeholder,
.stTextArea  > div > div > textarea::placeholder {
  color:rgba(240,237,232,.22) !important;
}
.stTextInput label, .stTextArea label { display:none !important; }
.stTextArea > div > div > textarea { resize:none !important; line-height:1.7 !important; }

/* buttons & form-submit */
.stButton > button,
.stFormSubmitButton > button {
  background:transparent !important;
  border:1px solid rgba(240,237,232,.18) !important;
  color:rgba(240,237,232,.55) !important;
  font-family:'DM Mono',monospace !important;
  font-size:10px !important;
  letter-spacing:.22em !important;
  text-transform:uppercase !important;
  padding:9px 26px !important;
  border-radius:0 !important;
  transition:all .2s ease !important;
  margin-top:16px !important;
}
.stButton > button:hover,
.stFormSubmitButton > button:hover {
  border-color:rgba(240,237,232,.65) !important;
  color:#F0EDE8 !important;
  background:transparent !important;
}
.stButton > button:disabled {
  opacity:.25 !important;
  cursor:not-allowed !important;
}

/* file uploader */
[data-testid="stFileUploader"] {
  border:1px dashed rgba(240,237,232,.15) !important;
  border-radius:0 !important;
  padding:16px !important;
  background:transparent !important;
}
[data-testid="stFileUploader"] label {
  font-family:'DM Mono',monospace !important;
  font-size:9px !important;
  letter-spacing:.2em !important;
  text-transform:uppercase !important;
  color:rgba(240,237,232,.3) !important;
}

/* checkboxes */
.stCheckbox > label {
  font-family:'DM Mono',monospace !important;
  font-size:9px !important;
  letter-spacing:.15em !important;
  text-transform:uppercase !important;
  color:rgba(240,237,232,.35) !important;
  gap:6px !important;
}

/* selectbox */
div[data-testid="stSelectbox"] > div > div {
  background:transparent !important;
  border-bottom:1px solid rgba(240,237,232,.12) !important;
  border-radius:0 !important;
  font-family:'DM Mono',monospace !important;
  font-size:11px !important;
}
div[data-testid="stSelectbox"] label {
  font-family:'DM Mono',monospace !important;
  font-size:9px !important;
  letter-spacing:.25em !important;
  text-transform:uppercase !important;
  color:rgba(240,237,232,.25) !important;
}

/* forms */
[data-testid="stForm"] { border:none !important; padding:0 !important; }

/* scrollable container */
[data-testid="stVerticalBlockBorderWrapper"] {
  background:transparent !important;
  border:none !important;
}

/* column gap */
[data-testid="stHorizontalBlock"] { gap:0 !important; }

/* scrollbar */
::-webkit-scrollbar { width:3px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:rgba(240,237,232,.07); }

/* image captions */
[data-testid="stImage"] p {
  font-family:'DM Mono',monospace !important;
  font-size:8px !important;
  color:rgba(240,237,232,.2) !important;
}

/* ── Roboto headings ──────────────────────────────────────────────────────── */
.sensi-heading {
  font-family:'Roboto',sans-serif !important;
  font-weight:300 !important;
  font-style:normal !important;
  font-size:clamp(20px,3vw,36px);
  line-height:1.4;
  color:#F0EDE8;
  text-align:center;
  margin:0 0 48px;
}

/* ── Progress bar ─────────────────────────────────────────────────────────── */
.prog-track {
  display:flex;
  align-items:center;
  gap:0;
  margin-bottom:8px;
}
.prog-seg {
  flex:1;
  height:1px;
  background:rgba(240,237,232,.08);
  position:relative;
  transition:background .3s ease;
}
.prog-seg.done  { background:rgba(240,237,232,.40); }
.prog-seg.active{ background:rgba(240,237,232,.75); }
.prog-seg::after {
  content:'';
  width:5px; height:5px;
  border-radius:50%;
  background:rgba(240,237,232,.12);
  position:absolute;
  top:-2px; right:-2.5px;
  transition:all .3s ease;
}
.prog-seg.done::after  { background:rgba(240,237,232,.45); }
.prog-seg.active::after{ background:#F0EDE8; box-shadow:0 0 6px rgba(240,237,232,.5); }
.prog-labels {
  display:flex;
  justify-content:space-between;
  margin-bottom:40px;
}
.prog-lbl {
  font-family:'DM Mono',monospace;
  font-size:7px;
  letter-spacing:.2em;
  text-transform:uppercase;
  color:rgba(240,237,232,.14);
  transition:color .3s ease;
}
.prog-lbl.active { color:rgba(240,237,232,.55); }

/* ── Radio-as-cards ───────────────────────────────────────────────────────── */
div[data-testid="stRadio"] > label { display:none !important; }
div[data-testid="stRadio"] > div {
  display:flex !important;
  gap:8px !important;
  flex-wrap:wrap !important;
}
div[data-testid="stRadio"] > div > label {
  flex:1 !important;
  min-width:80px !important;
  border:1px solid rgba(240,237,232,.10) !important;
  padding:14px 10px !important;
  text-align:center !important;
  cursor:pointer !important;
  border-radius:0 !important;
  transition:all .18s ease !important;
  font-family:'DM Mono',monospace !important;
  font-size:9px !important;
  letter-spacing:.18em !important;
  text-transform:uppercase !important;
  color:rgba(240,237,232,.35) !important;
}
div[data-testid="stRadio"] > div > label:hover {
  border-color:rgba(240,237,232,.35) !important;
  color:rgba(240,237,232,.75) !important;
  background:rgba(240,237,232,.02) !important;
}
div[data-testid="stRadio"] > div > label:has(input:checked) {
  border-color:rgba(240,237,232,.60) !important;
  color:#F0EDE8 !important;
  background:rgba(240,237,232,.05) !important;
}
/* hide radio circle */
div[data-testid="stRadio"] > div > label > div:first-child { display:none !important; }

/* ── Sense checkboxes (multi-select grid) ─────────────────────────────────── */
.sense-grid-wrap div[data-testid="stCheckbox"] > label {
  border:1px solid rgba(240,237,232,.08) !important;
  padding:10px 8px !important;
  width:100% !important;
  justify-content:center !important;
  border-radius:0 !important;
  font-family:'DM Mono',monospace !important;
  font-size:9px !important;
  letter-spacing:.15em !important;
  text-transform:uppercase !important;
  color:rgba(240,237,232,.28) !important;
  transition:all .15s ease !important;
  cursor:pointer !important;
}
.sense-grid-wrap div[data-testid="stCheckbox"] > label:hover {
  border-color:rgba(240,237,232,.25) !important;
  color:rgba(240,237,232,.6) !important;
}
/* hide native checkbox box */
.sense-grid-wrap div[data-testid="stCheckbox"] > label > span:first-child {
  display:none !important;
}
/* sense color overrides applied via per-sense wrapper classes */
.sense-thermal  div[data-testid="stCheckbox"] > label:has(input:checked){ border-color:#E8836A !important; color:#E8836A !important; background:rgba(232,131,106,.07) !important; }
.sense-visual   div[data-testid="stCheckbox"] > label:has(input:checked){ border-color:#D4B96A !important; color:#D4B96A !important; background:rgba(212,185,106,.07) !important; }
.sense-acoustic div[data-testid="stCheckbox"] > label:has(input:checked){ border-color:#9B8FD4 !important; color:#9B8FD4 !important; background:rgba(155,143,212,.07) !important; }
.sense-spatial  div[data-testid="stCheckbox"] > label:has(input:checked){ border-color:#6AB8C8 !important; color:#6AB8C8 !important; background:rgba(106,184,200,.07) !important; }
.sense-olfactory div[data-testid="stCheckbox"] > label:has(input:checked){ border-color:#8BB88A !important; color:#8BB88A !important; background:rgba(139,184,138,.07) !important; }
.sense-tactile  div[data-testid="stCheckbox"] > label:has(input:checked){ border-color:#C4A882 !important; color:#C4A882 !important; background:rgba(196,168,130,.07) !important; }

/* ── Pulse animation (loading overlay) ───────────────────────────────────── */
@keyframes pulse-ring {
  0%,100% { transform:scale(1);   border-color:rgba(240,237,232,.10); }
  50%      { transform:scale(1.10); border-color:rgba(240,237,232,.30); }
}
@keyframes pulse-core {
  0%,100% { opacity:.35; transform:translate(-50%,-50%) scale(1); }
  50%      { opacity:.80; transform:translate(-50%,-50%) scale(1.25); }
}
@keyframes pulse-outer {
  0%,100% { opacity:0; transform:scale(1); }
  50%      { opacity:.4; transform:scale(1.18); }
}
@keyframes msg-cycle {
  0%,18%  { opacity:.55; }
  22%,78% { opacity:.55; }
  82%,100%{ opacity:0;   }
}
</style>
""", unsafe_allow_html=True)


# ── paths ─────────────────────────────────────────────────────────────────────
_PERSONA_PATH = _TEAM_DIR / "persona.json"
_RESULTS_DIR  = _PYTHON_DIR / "resulting_layout"


# ── bootstrap (MCP connection cached per server session) ─────────────────────
@st.cache_resource
def _get_ctx():
    from _runtime.bootstrap import bootstrap
    return bootstrap()


# ── session initialisation ────────────────────────────────────────────────────
def _init():
    if "sensi_init" in st.session_state:
        return

    st.session_state.sensi_init             = True
    st.session_state.agent_session          = {}
    st.session_state.messages               = []
    st.session_state.scores                 = {}
    st.session_state.persona_reveal_confirmed = False

    if _PERSONA_PATH.exists():
        try:
            persona = json.loads(_PERSONA_PATH.read_text("utf-8"))
            name    = persona.get("name", "")
            st.session_state.agent_session = {
                "onboarding_complete": True,
                "greeted": True, "quiz_complete": True, "inspire_complete": True,
                "persona_profile": persona,
                "user_type": persona.get("role", "client"),
            }
            greeting = (
                f"Welcome back{', ' + name if name else ''}. "
                "Your comfort profile is loaded. "
                "Tell me which layout you'd like to explore — 201, 202, or 203."
            )
            st.session_state.messages = [{"role": "sensi", "content": greeting}]
            st.session_state.persona_reveal_confirmed = True  # already saw it in a prior session
            return
        except Exception:
            pass

    # new user — fire greet turn
    try:
        from graph import run_agent
        ctx = _get_ctx()
        response, session = run_agent("", ctx, {})
        st.session_state.agent_session = session
        st.session_state.messages      = [{"role": "sensi", "content": response}]
    except Exception as exc:
        st.session_state.messages = [{
            "role": "sensi",
            "content": f"Hi, I'm Sensi. Couldn't connect — check your terminal. ({exc})",
        }]


_init()


# ── agent call (with loading overlay) ────────────────────────────────────────
def _run(user_input: str, context: str = "general") -> str:
    from graph import run_agent
    ctx = _get_ctx()

    overlay = st.empty()
    overlay.markdown(
        _loading_html(_LOADING.get(context, _LOADING["general"])),
        unsafe_allow_html=True,
    )

    try:
        response, new_session = run_agent(
            user_input, ctx, st.session_state.agent_session
        )
    except Exception as exc:
        overlay.empty()
        return f"[error — {exc}]"

    overlay.empty()
    st.session_state.agent_session = new_session

    lid = new_session.get("layout_id")
    if lid:
        numeric = str(lid).replace("Layout-", "").replace("layout-", "").strip()
        f = _RESULTS_DIR / f"Layout-{numeric}_modified.json"
        if f.exists():
            try:
                data   = json.loads(f.read_text("utf-8"))
                scores = {}
                for room in data.get("rooms", []):
                    a  = room.get("attributes", {}).get("analysis", {})
                    cs = a.get("comfortScores", {})
                    if cs:
                        key         = room.get("name") or room.get("id", "room")
                        scores[key] = {"overallScore": a.get("overallScore", 0.0),
                                       "comfortScores": cs}
                if scores:
                    st.session_state.scores = scores
            except Exception:
                pass

    return response


# ── Plotly radar chart ────────────────────────────────────────────────────────
def _radar(room_name: str, room_data: dict):
    import plotly.graph_objects as go

    senses = ["thermal","visual","acoustic","spatial","olfactory","tactile"]
    labels = ["Thermal","Visual","Acoustic","Spatial","Olfactory","Tactile"]
    cs     = room_data.get("comfortScores", {})
    vals   = [float(cs.get(s, 0)) for s in senses]
    max_i  = vals.index(max(vals)) if any(v > 0 for v in vals) else 0
    lc     = _SC[senses[max_i]]

    fig = go.Figure(go.Scatterpolar(
        r=vals+[vals[0]], theta=labels+[labels[0]],
        fill="toself", fillcolor=_rgba(lc, 0.09),
        line=dict(color=lc, width=1.5), marker=dict(size=3, color=lc),
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0,1], visible=True, showticklabels=False,
                            gridcolor="rgba(240,237,232,.05)",
                            linecolor="rgba(240,237,232,.05)"),
            angularaxis=dict(tickfont=dict(family="DM Mono, monospace", size=8,
                                           color="rgba(240,237,232,.38)"),
                             gridcolor="rgba(240,237,232,.04)",
                             linecolor="rgba(240,237,232,.07)"),
        ),
        showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=36, r=36, t=10, b=10), height=210,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────────────────────────────────────────────────────────────────
# INSPIRE PIPELINE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _vlm_analyze(llm, images_b64: list[str], text_desc: str) -> str:
    """
    Ask the LLM to extract an aesthetic profile from reference images.
    Tries multimodal (vision) format first; falls back to text-only if the
    model doesn't support it (e.g. text-only Cloudflare Workers AI models).
    """
    from langchain_core.messages import HumanMessage

    SYSTEM = (
        "You are a spatial aesthetic analyst. Extract a rich sensory and visual "
        "profile from the provided reference images and/or description.\n\n"
        "Capture:\n"
        "  • Color palette — dominant hues, temperature (warm/cool), saturation\n"
        "  • Light quality — source (natural/artificial), quality (soft/harsh/diffuse/directional), tone\n"
        "  • Materials & textures — wood, stone, concrete, fabric, metal, plaster, plant\n"
        "  • Spatial mood — intimate/open, minimal/layered, calm/dynamic, raw/refined\n"
        "  • Atmosphere — time of day feel, level of cosiness vs. grandeur\n\n"
        "Write a specific, grounded aesthetic profile in 120–150 words. No lists. "
        "No headers. Just a flowing description."
    )

    # --- try multimodal (vision) ---
    if images_b64:
        content: list = [{"type": "text", "text": f"{SYSTEM}\n\nUser description: {text_desc}"}]
        for b64 in images_b64[:4]:           # keep under token budget
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
        try:
            resp = llm.invoke([HumanMessage(content=content)])
            result = resp.content.strip()
            print(f"[inspire_vlm] Vision analysis OK: {result[:60]}…")
            return result
        except Exception as exc:
            print(f"[inspire_vlm] Vision call failed ({exc}) — text-only fallback")

    # --- text-only fallback ---
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user",   "content": text_desc or "minimalist interior, warm and natural"},
    ]
    try:
        resp = llm.invoke(messages)
        result = resp.content.strip()
        print(f"[inspire_vlm] Text-only analysis OK: {result[:60]}…")
        return result
    except Exception as exc:
        print(f"[inspire_vlm] Text fallback also failed ({exc})")
        return f"Aesthetic preference: {text_desc}"


def _gen_queries(llm, analysis: str, prev_desc: str = "", n: int = 4) -> list[str]:
    """Generate n Unsplash search queries from an aesthetic analysis."""
    from langchain_core.messages import HumanMessage

    extra = (f"\n\nThe user particularly liked images suggesting: {prev_desc}" if prev_desc else "")
    prompt = (
        f"Aesthetic analysis:\n{analysis}{extra}\n\n"
        f"Generate {n} specific Unsplash search queries that would find interior "
        f"spaces matching this aesthetic. Be concrete: include materials, light "
        f"quality, mood words. Each query = 3–5 words.\n"
        f"Return ONLY a JSON array: [\"query1\", \"query2\", ...]"
    )
    defaults = [
        "minimal interior warm natural light",
        "calm architectural space texture",
        "serene material palette daylight",
        "intimate atmospheric room",
    ]
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        m = re.search(r"\[.*?\]", resp.content, re.DOTALL)
        if m:
            parsed = json.loads(m.group())
            if isinstance(parsed, list) and parsed:
                return [str(q) for q in parsed[:n]]
    except Exception as exc:
        print(f"[inspire_queries] Query gen failed ({exc}) — using defaults")
    return defaults[:n]


def _fetch_unsplash(queries: list[str], per_query: int = 3) -> tuple[list[str], list[str]]:
    """
    Fetch images from Unsplash.
    Returns (urls, descriptions) parallel lists.
    Requires UNSPLASH_ACCESS_KEY in env.  Returns ([], []) if key absent.
    """
    import httpx
    key = os.getenv("UNSPLASH_ACCESS_KEY", "")
    if not key:
        print("[unsplash] UNSPLASH_ACCESS_KEY not set — skipping fetch")
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
            else:
                print(f"[unsplash] {resp.status_code} for query '{q}'")
        except Exception as exc:
            print(f"[unsplash] Request failed for '{q}': {exc}")
    return urls, descs


def _picks_from_ss(prefix: str, n: int) -> list[int]:
    """Read which checkboxes are ticked for a given round prefix."""
    return [i for i in range(n) if st.session_state.get(f"{prefix}_{i}", False)]


def _clear_checks(prefix: str, n: int):
    """Clear checkbox state for a round (called before advancing)."""
    for i in range(n):
        st.session_state.pop(f"{prefix}_{i}", None)


def _inspire_init():
    """Initialise all inspire pipeline session_state keys (idempotent)."""
    defaults = {
        "inspire_stage":       "question",   # question | preparing | r1_show | r1_to_r2
                                              # r2_show | r2_to_r3 | r3_show | moodboard
        "inspire_text":        "",
        "inspire_b64s":        [],           # base64 strings of uploaded images
        "inspire_analysis":    "",           # VLM output
        "inspire_r1_urls":     [],
        "inspire_r1_descs":    [],
        "inspire_r2_urls":     [],
        "inspire_r2_descs":    [],
        "inspire_r3_urls":     [],
        "inspire_r3_descs":    [],
        "inspire_r1_picks":    [],           # selected urls after round 1
        "inspire_r2_picks":    [],
        "inspire_final_picks": [],           # final moodboard urls
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Inspire: header helper ────────────────────────────────────────────────────
def _inspire_header(label: str):
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:center;'
        f'gap:10px;margin-bottom:48px;">'
        f'{_LOGO_SVG}'
        f'<span style="font-family:DM Mono,monospace;font-size:9px;'
        f'letter-spacing:.38em;color:rgba(240,237,232,.18);'
        f'text-transform:uppercase;">{label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Inspire stage: question + upload ─────────────────────────────────────────
def _inspire_question():
    last = next(
        (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "sensi"),
        "Tell me about the spaces that move you.",
    )

    _, col, _ = st.columns([1, 3, 1])
    with col:
        st.markdown('<div style="padding-top:10vh;"></div>', unsafe_allow_html=True)
        _inspire_header("aesthetic · profile")

        st.markdown(
            f'<p class="fade-up sensi-heading" style="font-size:clamp(22px,3.5vw,44px);'
            f'font-weight:300;line-height:1.25;color:#F0EDE8;'
            f'text-align:center;margin:0 0 56px;">'
            f'{last}</p>',
            unsafe_allow_html=True,
        )

        with st.form("inspire_q_form", clear_on_submit=True):
            user_text = st.text_area(
                "description", placeholder="describe your ideal sensory world…",
                label_visibility="hidden", height=100,
            )
            uploads = st.file_uploader(
                "reference images (optional — up to 5)",
                accept_multiple_files=True,
                type=["jpg", "jpeg", "png", "webp"],
                label_visibility="visible",
            )
            submitted = st.form_submit_button("build my moodboard →")

        st.markdown('<div style="padding-bottom:10vh;"></div>', unsafe_allow_html=True)

    if submitted:
        text = user_text.strip() if user_text else ""
        b64s = []
        if uploads:
            for f in uploads[:5]:
                raw = f.read()
                b64s.append(base64.b64encode(raw).decode())

        st.session_state.inspire_text  = text
        st.session_state.inspire_b64s  = b64s
        st.session_state.inspire_stage = "preparing"
        st.rerun()


# ── Inspire stage: preparing (VLM + Unsplash round 1) ────────────────────────
def _inspire_preparing(label: str = "preparing",
                        next_stage: str = "r1_show",
                        refine_desc: str = ""):
    """
    Generic 'preparing' stage:
    - Shows loading overlay
    - Runs VLM analysis (first call only) and/or Unsplash query+fetch
    - Advances to next_stage
    """
    ctx = _get_ctx()
    llm = ctx.llm_simple

    overlay = st.empty()

    # Step 1: VLM analysis (only needed once, first prepare)
    if not st.session_state.inspire_analysis:
        overlay.markdown(_loading_html(_LOADING["vlm"]), unsafe_allow_html=True)
        analysis = _vlm_analyze(llm, st.session_state.inspire_b64s, st.session_state.inspire_text)
        st.session_state.inspire_analysis = analysis
    else:
        analysis = st.session_state.inspire_analysis

    # Step 2: Generate Unsplash queries
    overlay.markdown(_loading_html(_LOADING["queries"]), unsafe_allow_html=True)
    if next_stage == "r1_show":
        n_queries, per_q = 4, 3    # 12 candidates
    elif next_stage == "r2_show":
        n_queries, per_q = 3, 3    # 9 candidates (trimmed to 8)
    else:
        n_queries, per_q = 2, 3    # 6 candidates

    queries = _gen_queries(llm, analysis, prev_desc=refine_desc, n=n_queries)

    # Step 3: Fetch from Unsplash
    overlay.markdown(_loading_html(_LOADING["unsplash"]), unsafe_allow_html=True)
    urls, descs = _fetch_unsplash(queries, per_query=per_q)

    overlay.empty()

    # Store results
    if next_stage == "r1_show":
        st.session_state.inspire_r1_urls  = urls[:12]
        st.session_state.inspire_r1_descs = descs[:12]
    elif next_stage == "r2_show":
        st.session_state.inspire_r2_urls  = urls[:9]
        st.session_state.inspire_r2_descs = descs[:9]
    else:
        st.session_state.inspire_r3_urls  = urls[:6]
        st.session_state.inspire_r3_descs = descs[:6]

    # If Unsplash unavailable and this is round 1, use uploaded images directly
    if not urls and next_stage == "r1_show":
        if st.session_state.inspire_b64s:
            # uploaded images are already available — skip to moodboard
            st.session_state.inspire_final_picks = []  # b64s will be shown
            st.session_state.inspire_stage = "moodboard"
        else:
            # no images at all — skip straight to synthesis
            st.session_state.inspire_stage = "moodboard"
        st.rerun()
        return

    st.session_state.inspire_stage = next_stage
    st.rerun()



# -- Inspire stage: neural image grid + moodboard v2 ----------------------------------

# =============================================================================
# INSPIRE — NEURAL GRID + UPDATED MOODBOARD
# (replaces _picks_from_ss, _clear_checks, _inspire_grid, _inspire_moodboard)
# =============================================================================

def _neural_connections_svg(selected: list, n: int, n_cols: int = 3) -> str:
    """
    Build an SVG string with animated connection lines between selected nodes.
    Uses a 300x(rows*100) coordinate space that maps to the image grid.
    """
    if len(selected) < 2:
        return ""
    n_rows = max((n + n_cols - 1) // n_cols, 1)
    h = n_rows * 100

    def cx(i): return (i % n_cols) * 100 + 50
    def cy(i): return (i // n_cols) * 100 + 50

    lines = ""
    for a in selected:
        for b in selected:
            if b <= a:
                continue
            ax, ay = cx(a), cy(a)
            bx, by = cx(b), cy(b)
            lines += f'''
  <line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}"
        stroke="rgba(210,185,106,0.35)" stroke-width="1.2">
    <animate attributeName="stroke-opacity" values="0.1;0.5;0.1"
             dur="2.2s" repeatCount="indefinite"/>
  </line>
  <circle r="3" fill="rgba(210,185,106,0.7)">
    <animateMotion dur="2.4s" repeatCount="indefinite">
      <mpath/>
    </animateMotion>
  </circle>
  <circle r="2.5" fill="rgba(210,185,106,0.5)">
    <animateMotion dur="2.4s" begin="1.2s" repeatCount="indefinite">
      <mpath/>
    </animateMotion>
  </circle>'''
    # Pulse rings on selected nodes
    for i in selected:
        x, y = cx(i), cy(i)
        lines += f'''
  <circle cx="{x}" cy="{y}" r="34" fill="none"
          stroke="rgba(210,185,106,0.15)" stroke-width="1">
    <animate attributeName="r" values="34;42;34" dur="2s" repeatCount="indefinite"/>
    <animate attributeName="stroke-opacity" values="0.2;0;0.2" dur="2s" repeatCount="indefinite"/>
  </circle>'''

    return f'<svg viewBox="0 0 300 {h}" preserveAspectRatio="xMidYMid meet" style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:5;">{lines}</svg>'


def _inspire_neural_grid(
    round_num:  int,
    urls:       list,
    descs:      list,
    min_picks:  int,
    next_stage: str,
    store_key:  str,
):
    """
    Neural node image selection — replaces checkbox grid.
    Images appear as circular nodes; SVG connection lines link selected nodes.
    Selection tracked via st.session_state toggle buttons.
    """
    n       = min(len(urls), 9)
    sel_key = f"neural_sel_r{round_num}"
    if sel_key not in st.session_state:
        st.session_state[sel_key] = set()

    selected = st.session_state[sel_key]

    # ── Round indicator ───────────────────────────────────────────────────────
    st.markdown(
        f'<div style="position:fixed;top:28px;right:40px;font-family:DM Mono,monospace;'
        f'font-size:10px;letter-spacing:.15em;color:rgba(240,237,232,.22);z-index:999;">'
        f'round {round_num} of 3</div>',
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 10, 1])
    with col:
        st.markdown('<div style="padding-top:8vh;">', unsafe_allow_html=True)
        _inspire_header("aesthetic · selection")

        st.markdown(
            '<p class="sensi-heading" style="font-size:clamp(16px,2.2vw,26px);'
            'margin-bottom:8px;">which of these feel like you?</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p style="font-family:DM Mono,monospace;font-size:8px;letter-spacing:.2em;'
            'text-transform:uppercase;color:rgba(240,237,232,.2);text-align:center;'
            'margin-bottom:32px;">click nodes to activate · connections form between selections</p>',
            unsafe_allow_html=True,
        )

        if not urls:
            st.markdown(
                '<p style="text-align:center;color:rgba(240,237,232,.25);font-family:DM Mono,'
                'monospace;font-size:10px;letter-spacing:.2em;">no images available --'
                ' add UNSPLASH_ACCESS_KEY to .env</p>',
                unsafe_allow_html=True,
            )
            if st.button("continue -->", key=f"neural_skip_{round_num}"):
                st.session_state[store_key]     = []
                st.session_state.inspire_stage  = next_stage
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            return

        # ── Neural grid container ─────────────────────────────────────────────
        n_cols  = 3
        n_rows  = (n + n_cols - 1) // n_cols
        svg_h   = n_rows * 100
        conn_svg = _neural_connections_svg(list(selected), n, n_cols)

        # Outer wrapper — relative position so SVG overlay aligns to grid
        st.markdown(
            f'<div style="position:relative;width:100%;min-height:{svg_h}px;">'
            f'{conn_svg}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Image nodes in columns
        node_cols = st.columns(n_cols)
        for i, (url, desc) in enumerate(zip(urls[:n], descs[:n])):
            with node_cols[i % n_cols]:
                is_sel = i in selected
                border = "rgba(210,185,106,0.7)" if is_sel else "rgba(240,237,232,0.10)"
                glow   = "0 0 18px rgba(210,185,106,0.22)" if is_sel else "none"
                bg     = "rgba(210,185,106,0.06)" if is_sel else "rgba(240,237,232,0.03)"

                try:
                    st.markdown(
                        f'<div style="width:100%;aspect-ratio:1/1;border-radius:50%;'
                        f'overflow:hidden;border:1.5px solid {border};'
                        f'box-shadow:{glow};background:{bg};'
                        f'transition:all 0.2s ease;margin-bottom:6px;">'
                        f'<img src="{url}" style="width:100%;height:100%;'
                        f'object-fit:cover;display:block;border-radius:50%;"></div>',
                        unsafe_allow_html=True,
                    )
                except Exception:
                    st.markdown(
                        f'<div style="width:100%;aspect-ratio:1/1;border-radius:50%;'
                        f'border:1px dashed rgba(240,237,232,0.1);'
                        f'background:rgba(240,237,232,0.03);"></div>',
                        unsafe_allow_html=True,
                    )

                # Toggle button — minimal
                btn_lbl = "deactivate" if is_sel else "activate"
                if st.button(btn_lbl, key=f"node_{round_num}_{i}", use_container_width=True):
                    if i in selected:
                        selected.discard(i)
                    else:
                        selected.add(i)
                    st.session_state[sel_key] = selected
                    st.rerun()

        # ── Selection count + continue ────────────────────────────────────────
        n_sel = len(selected)
        verb  = "continue -->" if round_num < 3 else "build my moodboard -->"
        st.markdown(
            f'<p style="font-family:DM Mono,monospace;font-size:9px;letter-spacing:.2em;'
            f'color:rgba(240,237,232,.28);text-align:center;margin:24px 0 8px;">'
            f'{n_sel} activated · pick at least {min_picks}</p>',
            unsafe_allow_html=True,
        )
        if st.button(verb, key=f"neural_next_{round_num}", disabled=(n_sel < min_picks)):
            picked = sorted(selected)
            picked_urls = [urls[i] for i in picked if i < len(urls)]
            st.session_state[store_key]     = picked_urls
            st.session_state[sel_key]       = set()
            st.session_state.inspire_stage  = next_stage
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)


def _inspire_moodboard_v2():
    """
    Final moodboard — capped at 4-6 images, neural connections shown.
    Replaces _inspire_moodboard().
    """
    # Collect all picks across rounds, cap at 6
    r3 = st.session_state.get("inspire_final_picks", [])
    r2 = st.session_state.get("inspire_r2_picks", [])
    r1 = st.session_state.get("inspire_r1_picks", [])
    b64s = st.session_state.get("inspire_b64s", [])

    raw_picks = r3 or r2 or r1
    final     = raw_picks[:6] if raw_picks else []
    if len(final) < 4 and len(raw_picks) > len(final):
        final = raw_picks[:4]

    analysis = st.session_state.get("inspire_analysis", "")

    _, col, _ = st.columns([1, 4, 1])
    with col:
        st.markdown('<div style="padding-top:8vh;">', unsafe_allow_html=True)
        _inspire_header("your moodboard")

        # Connection SVG + circular images
        n = len(final) or len(b64s)
        if n > 0:
            all_sel = list(range(n))
            conn_svg = _neural_connections_svg(all_sel, n, min(n, 3))
            st.markdown(
                f'<div style="position:relative;width:100%;">'
                f'{conn_svg}</div>',
                unsafe_allow_html=True,
            )

        if final:
            n_cols = min(len(final), 3)
            img_cols = st.columns(n_cols)
            for i, url in enumerate(final):
                with img_cols[i % n_cols]:
                    try:
                        st.markdown(
                            f'<div style="width:100%;aspect-ratio:1/1;border-radius:50%;'
                            f'overflow:hidden;border:1px solid rgba(210,185,106,0.3);'
                            f'margin-bottom:8px;">'
                            f'<img src="{url}" style="width:100%;height:100%;'
                            f'object-fit:cover;border-radius:50%;"></div>',
                            unsafe_allow_html=True,
                        )
                    except Exception:
                        pass
        elif b64s:
            n_cols = min(len(b64s[:6]), 3)
            img_cols = st.columns(n_cols)
            for i, b64 in enumerate(b64s[:6]):
                with img_cols[i % n_cols]:
                    st.markdown(
                        f'<div style="width:100%;aspect-ratio:1/1;border-radius:50%;'
                        f'overflow:hidden;border:1px solid rgba(240,237,232,0.1);'
                        f'margin-bottom:8px;">'
                        f'<img src="data:image/jpeg;base64,{b64}" '
                        f'style="width:100%;height:100%;object-fit:cover;'
                        f'border-radius:50%;"></div>',
                        unsafe_allow_html=True,
                    )
        else:
            st.markdown(
                '<p class="sensi-heading" style="opacity:0.2;font-size:18px;">'
                'Your aesthetic lives in words -- no images, but the feeling is clear.</p>',
                unsafe_allow_html=True,
            )

        # Aesthetic reading
        if analysis:
            st.markdown(
                f'<div style="margin:40px 0 32px;padding:24px 28px;'
                f'border-left:1px solid rgba(240,237,232,.1);">'
                f'<p style="font-family:DM Mono,monospace;font-size:8px;letter-spacing:.25em;'
                f'text-transform:uppercase;color:rgba(240,237,232,.2);margin:0 0 12px;">'
                f'aesthetic reading</p>'
                f'<p style="font-family:Roboto,sans-serif;font-weight:300;font-size:15px;'
                f'line-height:1.75;color:rgba(240,237,232,.6);">{analysis}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div style="text-align:center;margin:8px 0 80px;">', unsafe_allow_html=True)
        if st.button("this is my aesthetic -->"):
            _inspire_approve(final, b64s, analysis)
        st.markdown('</div></div>', unsafe_allow_html=True)



def _inspire_approve(final_picks: list[str], b64s: list[str], analysis: str):
    """
    Called when user approves moodboard.
    Persists image analysis into agent_session, then calls the graph
    inspire node (synthesis sub-step B) to produce inspire_summary.
    """
    # Build rich context for graph synthesis
    n_picks = len(final_picks) or len(b64s)
    context = (
        f"{st.session_state.inspire_text}\n\n"
        f"[Moodboard context: user selected {n_picks} reference image(s) "
        f"across aesthetic refinement rounds.]"
    )

    # Inject image analysis into agent_session BEFORE calling run_agent
    st.session_state.agent_session["inspire_image_analysis"] = analysis
    st.session_state.agent_session["inspire_moodboard_urls"] = final_picks

    # inspire_prompted is already True (set by graph during last quiz turn)
    # Graph will route to inspire → sub-step B (synthesis) → persona_compiler
    resp = _run(context, context="inspire")
    st.session_state.messages.append({"role": "sensi", "content": resp})
    st.rerun()


# ── Inspire: main orchestrator ────────────────────────────────────────────────
def _inspire():
    _inspire_init()
    stage = st.session_state.inspire_stage

    if stage == "question":
        _inspire_question()

    elif stage == "preparing":
        _inspire_preparing(next_stage="r1_show")

    elif stage == "r1_show":
        _inspire_neural_grid(
            round_num=1, urls=st.session_state.inspire_r1_urls,
            descs=st.session_state.inspire_r1_descs,
            min_picks=2, next_stage="r1_to_r2", store_key="inspire_r1_picks",
        )

    elif stage == "r1_to_r2":
        picks     = st.session_state.inspire_r1_picks
        pick_descs = st.session_state.inspire_r1_descs
        selected_descs = [
            d for url, d in zip(st.session_state.inspire_r1_urls, pick_descs)
            if url in picks
        ]
        refine_desc = "; ".join(selected_descs[:4]) if selected_descs else ""
        _inspire_preparing(next_stage="r2_show", refine_desc=refine_desc)

    elif stage == "r2_show":
        _inspire_neural_grid(
            round_num=2, urls=st.session_state.inspire_r2_urls,
            descs=st.session_state.inspire_r2_descs,
            min_picks=2, next_stage="r2_to_r3", store_key="inspire_r2_picks",
        )

    elif stage == "r2_to_r3":
        picks     = st.session_state.inspire_r2_picks
        pick_descs = st.session_state.inspire_r2_descs
        selected_descs = [
            d for url, d in zip(st.session_state.inspire_r2_urls, pick_descs)
            if url in picks
        ]
        refine_desc = "; ".join(selected_descs[:3]) if selected_descs else ""
        _inspire_preparing(next_stage="r3_show", refine_desc=refine_desc)

    elif stage == "r3_show":
        _inspire_neural_grid(
            round_num=3, urls=st.session_state.inspire_r3_urls,
            descs=st.session_state.inspire_r3_descs,
            min_picks=2, next_stage="moodboard", store_key="inspire_final_picks",
        )

    elif stage == "moodboard":
        _inspire_moodboard_v2()


# ─────────────────────────────────────────────────────────────────────────────

# =============================================================================
# SCREEN 2.5 -- PERSONA REVEAL
# Shown once after persona_compiler runs, before analysis mode unlocks.
# User reads their compiled profile and clicks confirm.
# =============================================================================

_SENSE_COLORS = {
    "thermal":   "#E8836A",
    "visual":    "#A8C5A0",
    "acoustic":  "#7EB8C9",
    "spatial":   "#C5A87E",
    "olfactory": "#B89EC5",
    "tactile":   "#C5BC9E",
}
_ROLE_COLORS = {
    "architect": "#7EB8C9",
    "student":   "#A8C5A0",
    "client":    "#C5A87E",
}


def _reveal_header():
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:center;'
        f'gap:10px;margin-bottom:56px;padding-top:6vh;">'
        f'{_LOGO_SVG}'
        f'<span style="font-family:DM Mono,monospace;font-size:9px;'
        f'letter-spacing:.38em;text-transform:uppercase;'
        f'color:rgba(240,237,232,.18);">persona · profile</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _persona_reveal():
    profile = st.session_state.agent_session.get("persona_profile") or {}

    # Pull fields
    name         = profile.get("name", "there") or "there"
    role         = profile.get("role", "client") or "client"
    description  = profile.get("description", "")
    priorities   = profile.get("sensory_priorities") or []
    weights      = profile.get("comfort_weights") or {}
    aesthetic    = profile.get("aesthetic_preferences", "")
    requirements = profile.get("key_requirements") or []

    # Moodboard images from inspire picks
    r3 = st.session_state.get("inspire_final_picks") or []
    r2 = st.session_state.get("inspire_r2_picks") or []
    r1 = st.session_state.get("inspire_r1_picks") or []
    mood_urls = (r3 or r2 or r1)[:6]

    role_color = _ROLE_COLORS.get(role, "#C5A87E")

    _, col, _ = st.columns([1, 7, 1])
    with col:
        _reveal_header()

        # ── Greeting ──────────────────────────────────────────────────────
        st.markdown(
            f'<p class="sensi-heading" style="font-size:clamp(28px,4vw,52px);'
            f'font-weight:200;color:#F0EDE8;text-align:center;margin:0 0 6px;">'
            f'Hi, {name}.</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p style="font-family:DM Mono,monospace;font-size:10px;'
            f'letter-spacing:.22em;text-transform:uppercase;'
            f'color:rgba(240,237,232,.25);text-align:center;margin:0 0 48px;">'
            f"here's what I've learned about you</p>",
            unsafe_allow_html=True,
        )

        # ── Role badge ────────────────────────────────────────────────────
        st.markdown(
            f'<div style="display:flex;justify-content:center;margin-bottom:24px;">'
            f'<span style="font-family:DM Mono,monospace;font-size:9px;'
            f'letter-spacing:.3em;text-transform:uppercase;padding:6px 16px;'
            f'border:1px solid {role_color};color:{role_color};border-radius:2px;">'
            f'{role}</span></div>',
            unsafe_allow_html=True,
        )

        # ── Description ───────────────────────────────────────────────────
        if description:
            st.markdown(
                f'<p style="font-family:Roboto,sans-serif;font-weight:300;'
                f'font-size:17px;line-height:1.7;color:rgba(240,237,232,.65);'
                f'text-align:center;max-width:560px;margin:0 auto 48px;">'
                f'{description}</p>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<hr style="border:none;border-top:1px solid rgba(240,237,232,.06);'
            'margin:0 0 40px;">',
            unsafe_allow_html=True,
        )

        # ── Sensory priorities ────────────────────────────────────────────
        st.markdown(
            '<p style="font-family:DM Mono,monospace;font-size:8px;'
            'letter-spacing:.28em;text-transform:uppercase;'
            'color:rgba(240,237,232,.2);margin:0 0 16px;">'
            'sensory priorities</p>',
            unsafe_allow_html=True,
        )
        pills_html = ""
        for i, sense in enumerate(priorities[:3]):
            c = _SENSE_COLORS.get(sense, "#C5A87E")
            pills_html += (
                f'<span style="font-family:DM Mono,monospace;font-size:9px;'
                f'letter-spacing:.2em;text-transform:uppercase;padding:5px 14px;'
                f'border:1px solid {c};color:{c};border-radius:2px;margin-right:8px;">'
                f'{sense}</span>'
            )
        if len(priorities) > 3:
            rest = len(priorities) - 3
            pills_html += (
                f'<span style="font-family:DM Mono,monospace;font-size:9px;'
                f'letter-spacing:.15em;color:rgba(240,237,232,.2);'
                f'padding:5px 0;">+{rest} more</span>'
            )
        st.markdown(
            f'<div style="margin-bottom:40px;">{pills_html}</div>',
            unsafe_allow_html=True,
        )

        # ── Comfort weight bars ───────────────────────────────────────────
        if weights:
            st.markdown(
                '<p style="font-family:DM Mono,monospace;font-size:8px;'
                'letter-spacing:.28em;text-transform:uppercase;'
                'color:rgba(240,237,232,.2);margin:0 0 16px;">'
                'comfort weights</p>',
                unsafe_allow_html=True,
            )
            bar_html = ""
            sense_order = ["thermal", "visual", "acoustic", "spatial", "olfactory", "tactile"]
            for sense in sense_order:
                w = weights.get(sense, 0.5)
                pct = int(w * 100)
                c = _SENSE_COLORS.get(sense, "#C5A87E")
                bar_html += (
                    f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">'
                    f'<span style="font-family:DM Mono,monospace;font-size:8px;'
                    f'letter-spacing:.15em;text-transform:uppercase;width:72px;'
                    f'color:rgba(240,237,232,.35);">{sense}</span>'
                    f'<div style="flex:1;height:3px;background:rgba(240,237,232,.06);'
                    f'border-radius:2px;overflow:hidden;">'
                    f'<div style="width:{pct}%;height:100%;background:{c};'
                    f'border-radius:2px;transition:width 0.6s ease;"></div></div>'
                    f'<span style="font-family:DM Mono,monospace;font-size:8px;'
                    f'color:rgba(240,237,232,.2);width:28px;text-align:right;">'
                    f'{w:.1f}</span>'
                    f'</div>'
                )
            st.markdown(
                f'<div style="margin-bottom:40px;">{bar_html}</div>',
                unsafe_allow_html=True,
            )

        # ── Moodboard strip ───────────────────────────────────────────────
        if mood_urls:
            st.markdown(
                '<hr style="border:none;border-top:1px solid rgba(240,237,232,.06);'
                'margin:0 0 32px;">',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p style="font-family:DM Mono,monospace;font-size:8px;'
                'letter-spacing:.28em;text-transform:uppercase;'
                'color:rgba(240,237,232,.2);margin:0 0 16px;">your moodboard</p>',
                unsafe_allow_html=True,
            )
            n = min(len(mood_urls), 6)
            strip_html = '<div style="display:flex;gap:10px;margin-bottom:40px;">'
            for url in mood_urls[:n]:
                strip_html += (
                    f'<div style="flex:1;aspect-ratio:1/1;border-radius:50%;'
                    f'overflow:hidden;border:1px solid rgba(240,237,232,.1);">'
                    f'<img src="{url}" style="width:100%;height:100%;'
                    f'object-fit:cover;border-radius:50%;display:block;"></div>'
                )
            strip_html += '</div>'
            st.markdown(strip_html, unsafe_allow_html=True)

        # ── Aesthetic preferences ─────────────────────────────────────────
        if aesthetic:
            st.markdown(
                f'<div style="padding:20px 24px;border-left:1px solid '
                f'rgba(240,237,232,.1);margin-bottom:40px;">'
                f'<p style="font-family:DM Mono,monospace;font-size:8px;'
                f'letter-spacing:.25em;text-transform:uppercase;'
                f'color:rgba(240,237,232,.18);margin:0 0 10px;">aesthetic</p>'
                f'<p style="font-family:Roboto,sans-serif;font-weight:300;'
                f'font-size:15px;line-height:1.75;color:rgba(240,237,232,.55);">'
                f'{aesthetic}</p></div>',
                unsafe_allow_html=True,
            )

        # ── Key requirements ──────────────────────────────────────────────
        if requirements:
            req_html = "".join(
                f'<li style="font-family:DM Mono,monospace;font-size:9px;'
                f'letter-spacing:.12em;color:rgba(240,237,232,.4);'
                f'margin-bottom:6px;">{r}</li>'
                for r in requirements
            )
            st.markdown(
                f'<div style="margin-bottom:40px;">'
                f'<p style="font-family:DM Mono,monospace;font-size:8px;'
                f'letter-spacing:.28em;text-transform:uppercase;'
                f'color:rgba(240,237,232,.2);margin:0 0 12px;">non-negotiables</p>'
                f'<ul style="list-style:none;padding:0;margin:0;">{req_html}</ul>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ── Stated preferences note ───────────────────────────────────────
        st.markdown(
            '<hr style="border:none;border-top:1px solid rgba(240,237,232,.06);'
            'margin:0 0 28px;">',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="padding:16px 20px;background:rgba(240,237,232,.03);'
            'border-radius:3px;margin-bottom:48px;">'
            '<p style="font-family:DM Mono,monospace;font-size:8px;'
            'letter-spacing:.22em;text-transform:uppercase;'
            'color:rgba(240,237,232,.18);margin:0 0 8px;">'
            'stated preferences vs comfort research</p>'
            '<p style="font-family:Roboto,sans-serif;font-weight:300;'
            'font-size:12px;line-height:1.7;color:rgba(240,237,232,.35);">'
            'Sensi treats what you told me as your starting point -- not a prescription. '
            'As we analyze your layouts, I will cross-reference your stated preferences '
            'with evidence-based comfort research. Where they align, we confirm. '
            'Where they diverge, I will flag it -- so you can decide with full information.'
            '</p></div>',
            unsafe_allow_html=True,
        )

        # ── Confirm button ────────────────────────────────────────────────
        st.markdown(
            '<div style="display:flex;justify-content:center;margin-bottom:80px;">',
            unsafe_allow_html=True,
        )
        if st.button("this is me  →"):
            st.session_state.persona_reveal_confirmed = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)



# SCREEN ROUTING
# ─────────────────────────────────────────────────────────────────────────────
def _screen() -> str:
    s = st.session_state.agent_session
    if s.get("onboarding_complete"):
        # Show persona reveal once before entering analysis
        if not st.session_state.get("persona_reveal_confirmed"):
            return "persona_reveal"
        return "analysis"
    if s.get("quiz_complete"):        return "inspire"
    return "quiz"

# ─────────────────────────────────────────────────────────────────────────────
# SCREEN 3 — ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
def _analysis():
    scores   = st.session_state.scores
    messages = st.session_state.messages

    submitted    = False
    user_input   = ""
    load_clicked = False

    chat_col, score_col = st.columns(2)

    # ── LEFT: chat ─────────────────────────────────────────────────────────
    with chat_col:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;'
            f'padding:28px 36px 16px;">'
            f'{_LOGO_SVG}'
            f'<span style="font-family:DM Mono,monospace;font-size:9px;'
            f'letter-spacing:.3em;text-transform:uppercase;'
            f'color:rgba(240,237,232,.16);">sensi</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        with st.container(height=680, border=False):
            for msg in messages:
                if msg["role"] == "sensi":
                    st.markdown(
                        f'<div class="fade-up sensi-heading" style="'
                        f'font-size:17px;font-weight:300;line-height:1.78;'
                        f'color:#F0EDE8;margin:0 36px 28px;">'
                        f'{msg["content"]}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div style="font-family:DM Sans,sans-serif;'
                        f'font-size:13px;font-weight:300;line-height:1.65;'
                        f'color:rgba(240,237,232,.40);'
                        f'margin:0 36px 28px;padding-left:14px;'
                        f'border-left:1px solid rgba(240,237,232,.08);">'
                        f'{msg["content"]}</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown(
            '<div style="height:1px;background:rgba(240,237,232,.04);'
            'margin:4px 36px 0;"></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 36px;">', unsafe_allow_html=True)
        with st.form("chat_form", clear_on_submit=True):
            user_input = st.text_input(
                "chat",
                placeholder="ask Sensi anything about this layout…",
                label_visibility="hidden",
            )
            submitted = st.form_submit_button("send →")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── RIGHT: scores ──────────────────────────────────────────────────────
    with score_col:
        st.markdown(
            '<div style="border-left:1px solid rgba(240,237,232,.05);'
            'min-height:100vh;padding:28px 36px;">',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<p style="font-family:DM Mono,monospace;font-size:9px;'
            'letter-spacing:.3em;text-transform:uppercase;'
            'color:rgba(240,237,232,.16);margin:0 0 28px;">'
            'comfort · scores</p>',
            unsafe_allow_html=True,
        )

        layout_choice = st.selectbox("LAYOUT", ["201","202","203"], key="layout_sel")
        if st.button("load layout"):
            load_clicked = True

        legend_html = '<div style="display:flex;flex-wrap:wrap;gap:12px 20px;margin:28px 0 24px;">'
        for sense, color in _SC.items():
            legend_html += (
                f'<span style="font-family:DM Mono,monospace;font-size:9px;'
                f'letter-spacing:.12em;text-transform:uppercase;color:{color};">'
                f'{_SI[sense]} {sense}</span>'
            )
        legend_html += "</div>"
        st.markdown(legend_html, unsafe_allow_html=True)

        if scores:
            for rname, rdata in scores.items():
                overall = rdata.get("overallScore", 0.0)
                st.markdown(
                    f'<p style="font-family:DM Sans,sans-serif;font-size:12px;'
                    f'font-weight:300;letter-spacing:.05em;'
                    f'color:rgba(240,237,232,.50);margin:24px 0 2px;">{rname}</p>'
                    f'<p style="font-family:DM Mono,monospace;font-size:10px;'
                    f'color:rgba(240,237,232,.22);margin:0;">{overall:.2f} overall</p>',
                    unsafe_allow_html=True,
                )
                _radar(rname, rdata)
        else:
            st.markdown(
                '<p class="sensi-heading" style="font-size:19px;font-weight:300;'
                'line-height:1.65;color:rgba(240,237,232,.10);margin-top:40px;">'
                'Scores appear here once you run a comfort analysis.</p>',
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

    # ── handle events ──────────────────────────────────────────────────────
    if load_clicked:
        msg_text = f"Let's look at layout {layout_choice}."
        st.session_state.messages.append({"role": "user",  "content": msg_text})
        resp = _run(msg_text, context="load")
        st.session_state.messages.append({"role": "sensi", "content": resp})
        st.rerun()

    if submitted and user_input.strip():
        ctx = _infer_context(user_input)
        st.session_state.messages.append({"role": "user",  "content": user_input.strip()})
        resp = _run(user_input.strip(), context=ctx)
        st.session_state.messages.append({"role": "sensi", "content": resp})
        st.rerun()



# =============================================================================
# QUIZ HELPERS + SCREEN 1
# =============================================================================

_QUIZ_STEP_NAMES = [
    "identity", "role", "your space", "senses", "your world", "non-negotiable"
]

_ROLE_OPTIONS = [
    ("I design spaces",    "architect"),
    ("I live in them",     "client"),
    ("I am here to learn", "student"),
]

_SENSE_OPTIONS = [
    ("thermal",   "#E8836A", "heat / cold"),
    ("visual",    "#D4B96A", "light / glare"),
    ("acoustic",  "#9B8FD4", "noise"),
    ("spatial",   "#6AB8C8", "feeling cramped"),
    ("olfactory", "#8BB88A", "air quality"),
    ("tactile",   "#C4A882", "surfaces / drafts"),
]

_LIFE_STAGE_OPTIONS = ["20s-30s", "30s-40s", "40s+"]
_LIVING_OPTIONS     = ["just me", "partner", "family", "flatmates", "other..."]


def _quiz_neuron_canvas(step: int):
    """Inject a neuron canvas that grows denser with each step."""
    node_count = 12 + step * 6
    import streamlit.components.v1 as components
    components.html(f"""
<canvas id="nc" style="position:fixed;top:0;left:0;width:100vw;height:100vh;
  pointer-events:none;z-index:0;opacity:0.22;"></canvas>
<script>
(function(){{
  var c=document.getElementById('nc');
  if(!c) return;
  var ctx=c.getContext('2d'), N={node_count}, W, H, nodes=[];
  function resize(){{
    W=c.width=window.innerWidth; H=c.height=window.innerHeight; nodes=[];
    for(var i=0;i<N;i++) nodes.push({{
      x:Math.random()*W, y:Math.random()*H,
      vx:(Math.random()-.5)*.35, vy:(Math.random()-.5)*.35,
      r:Math.random()*1.2+.4
    }});
  }}
  resize(); window.addEventListener('resize',resize);
  function draw(){{
    ctx.clearRect(0,0,W,H);
    for(var i=0;i<N;i++){{
      var a=nodes[i]; a.x+=a.vx; a.y+=a.vy;
      if(a.x<0||a.x>W) a.vx*=-1;
      if(a.y<0||a.y>H) a.vy*=-1;
      for(var j=i+1;j<N;j++){{
        var b=nodes[j], d=Math.hypot(a.x-b.x,a.y-b.y);
        if(d<90){{
          ctx.strokeStyle='rgba(240,237,232,'+(0.14*(1-d/90))+')';
          ctx.lineWidth=.5;
          ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
        }}
      }}
      ctx.fillStyle='rgba(240,237,232,.45)';
      ctx.beginPath();ctx.arc(a.x,a.y,a.r,0,Math.PI*2);ctx.fill();
    }}
    requestAnimationFrame(draw);
  }}
  draw();
}})();
</script>
""", height=0, scrolling=False)


def _quiz_progress(step: int):
    """Render named progress bar for the 6 quiz steps."""
    segs = ""
    for i in range(6):
        cls = "done" if i < step else ("active" if i == step else "")
        segs += f'<div class="prog-seg {cls}"></div>'
    labels = ""
    for i, name in enumerate(_QUIZ_STEP_NAMES):
        cls = "active" if i == step else ""
        labels += f'<span class="prog-lbl {cls}">{name}</span>'
    st.markdown(
        f'<div class="prog-track">{segs}</div>'
        f'<div class="prog-labels">{labels}</div>',
        unsafe_allow_html=True,
    )


def _quiz_logo():
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:center;'
        f'gap:10px;margin-bottom:36px;">'
        f'{_LOGO_SVG}'
        f'<span style="font-family:DM Mono,monospace;font-size:10px;'
        f'letter-spacing:.32em;color:rgba(240,237,232,.18);'
        f'text-transform:uppercase;">sensi</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _format_role(role_key: str) -> str:
    mapping = {
        "architect": "I design spaces -- architect",
        "client":    "I live in spaces -- client",
        "student":   "I am here to learn -- student",
    }
    return mapping.get(role_key, role_key)


def _format_senses(selected: list) -> str:
    if not selected:
        return "No specific sensory bothers mentioned."
    return "The senses that pull me out of comfort: " + ", ".join(selected) + "."


def _format_life(stage: str, living: str, other_text: str) -> str:
    living_detail = other_text.strip() if living == "other..." and other_text.strip() else living
    return f"Life stage: {stage}. Living situation: {living_detail}."


# -----------------------------------------------------------------------------
# SCREEN 1 -- QUIZ (redesigned)
# -----------------------------------------------------------------------------

def _quiz():
    sess      = st.session_state.agent_session
    step      = sess.get("quiz_step", 0)

    last_msg = next(
        (m["content"] for m in reversed(st.session_state.messages)
         if m["role"] == "sensi"),
        "Hi, I'm Sensi. What's your name?",
    )

    # Neuron canvas background
    _quiz_neuron_canvas(step)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
            '<div style="padding-top:10vh;position:relative;z-index:1;">',
            unsafe_allow_html=True,
        )

        _quiz_logo()
        _quiz_progress(step)

        st.markdown(
            f'<p class="sensi-heading fade-up">{last_msg}</p>',
            unsafe_allow_html=True,
        )

        submitted  = False
        user_input = ""

        # -- Steps 0, 2, 5: text input / textarea ----------------------------
        if step in (0, 2, 5):
            btn_label = "build my profile -->" if step == 5 else "continue -->"
            ph = {
                0: "your name",
                2: "could be anywhere -- a room, a cafe, a corner of the world...",
                5: "e.g. natural light, silence, warmth...",
            }[step]
            with st.form(f"quiz_form_{step}", clear_on_submit=True):
                if step == 2:
                    user_input = st.text_area(
                        "answer", placeholder=ph,
                        label_visibility="hidden", height=90,
                    )
                else:
                    user_input = st.text_input(
                        "answer", placeholder=ph, label_visibility="hidden",
                    )
                submitted = st.form_submit_button(btn_label)

        # -- Step 1: role card picker (radio styled as cards) -----------------
        elif step == 1:
            role_sel = st.radio(
                "role",
                [opt[0] for opt in _ROLE_OPTIONS],
                key="quiz_role",
                label_visibility="hidden",
            )
            if st.button("continue -->", key="quiz_role_btn"):
                role_key   = next((v for l, v in _ROLE_OPTIONS if l == role_sel), "client")
                user_input = _format_role(role_key)
                submitted  = True

        # -- Step 3: sense multi-select grid ----------------------------------
        elif step == 3:
            st.markdown(
                '<p style="font-family:DM Mono,monospace;font-size:8px;'
                'letter-spacing:.22em;text-transform:uppercase;'
                'color:rgba(240,237,232,.22);text-align:center;margin-bottom:16px;">'
                'select all that apply</p>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="sense-grid-wrap">', unsafe_allow_html=True)
            cols3 = st.columns(3)
            for i, (sense, color, label) in enumerate(_SENSE_OPTIONS):
                with cols3[i % 3]:
                    st.markdown(f'<div class="sense-{sense}">', unsafe_allow_html=True)
                    st.checkbox(f"{_SI[sense]}  {sense}", key=f"sense_sel_{sense}")
                    st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("continue -->", key="quiz_sense_btn"):
                selected   = [s for s, _, _ in _SENSE_OPTIONS
                              if st.session_state.get(f"sense_sel_{s}", False)]
                user_input = _format_senses(selected)
                submitted  = True

        # -- Step 4: life stage + living situation ----------------------------
        elif step == 4:
            st.markdown(
                '<p style="font-family:DM Mono,monospace;font-size:8px;'
                'letter-spacing:.22em;text-transform:uppercase;'
                'color:rgba(240,237,232,.22);text-align:center;margin-bottom:8px;">'
                'life stage</p>',
                unsafe_allow_html=True,
            )
            stage_sel = st.radio(
                "stage", _LIFE_STAGE_OPTIONS,
                key="quiz_stage", label_visibility="hidden",
            )
            st.markdown(
                '<p style="font-family:DM Mono,monospace;font-size:8px;'
                'letter-spacing:.22em;text-transform:uppercase;'
                'color:rgba(240,237,232,.22);text-align:center;'
                'margin:20px 0 8px;">who do you share your home with?</p>',
                unsafe_allow_html=True,
            )
            living_sel = st.radio(
                "living", _LIVING_OPTIONS,
                key="quiz_living", label_visibility="hidden",
            )
            other_text = ""
            if living_sel == "other...":
                other_text = st.text_input(
                    "specify", placeholder="tell us a bit more...",
                    key="quiz_living_other", label_visibility="hidden",
                )
            if st.button("continue -->", key="quiz_life_btn"):
                user_input = _format_life(
                    stage_sel or _LIFE_STAGE_OPTIONS[0],
                    living_sel or _LIVING_OPTIONS[0],
                    other_text,
                )
                submitted = True

        st.markdown('</div>', unsafe_allow_html=True)

    # -- Submit ----------------------------------------------------------------
    if submitted and (user_input or "").strip():
        text = user_input.strip()
        st.session_state.messages.append({"role": "user", "content": text})
        resp = _run(text, context="quiz")
        st.session_state.messages.append({"role": "sensi", "content": resp})
        st.rerun()

# ── main ───────────────────────────

_init()
screen = _screen()
if   screen == "quiz":           _quiz()
elif screen == "inspire":        _inspire()
elif screen == "persona_reveal": _persona_reveal()
else:                            _analysis()
