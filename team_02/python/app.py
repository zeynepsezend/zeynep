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
def _loading_html(msg: str) -> str:
    return f"""
<div style="position:fixed;top:0;left:0;right:0;bottom:0;
            background:rgba(13,13,13,0.93);z-index:9998;
            display:flex;flex-direction:column;
            align-items:center;justify-content:center;gap:0;">
  <p style="font-family:'DM Mono',monospace;font-size:9px;
            letter-spacing:.35em;text-transform:uppercase;
            color:rgba(240,237,232,.18);margin:0 0 36px;">sensi</p>
  <div style="width:1px;height:48px;
              background:linear-gradient(to bottom,transparent,rgba(240,237,232,.25),transparent);
              margin-bottom:36px;"></div>
  <p style="font-family:'DM Serif Display',serif;font-style:italic;
            font-size:20px;color:rgba(240,237,232,.55);
            text-align:center;margin:0;max-width:340px;line-height:1.5;">{msg}</p>
</div>
"""

# ── global CSS ────────────────────────────────────────────────────────────────
st.markdown(r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;1,9..40,300&family=DM+Mono:wght@300&display=swap');

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

    st.session_state.sensi_init    = True
    st.session_state.agent_session = {}
    st.session_state.messages      = []
    st.session_state.scores        = {}

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
            f'<p class="fade-up" style="font-family:\'DM Serif Display\',serif;'
            f'font-style:italic;font-size:clamp(22px,3.5vw,44px);'
            f'line-height:1.25;color:#F0EDE8;text-align:center;margin:0 0 56px;">'
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


# ── Inspire stage: image selection grid ──────────────────────────────────────
def _inspire_grid(
    rnd: int,
    urls: list[str],
    descs: list[str],
    n_cols: int,
    min_picks: int,
    next_stage: str,
    store_key: str,
):
    """
    Render a selection grid for one moodboard round.
    rnd        : round number (1, 2, 3)
    urls       : candidate image URLs
    descs      : alt descriptions (parallel to urls)
    n_cols     : grid columns
    min_picks  : minimum selections to enable "Next" button
    next_stage : stage to advance to on continue
    store_key  : session_state key to store picked URLs
    """
    prefix = f"r{rnd}"
    n      = len(urls)

    # progress indicator
    st.markdown(
        f'<div style="position:fixed;top:28px;right:40px;'
        f'font-family:DM Mono,monospace;font-size:10px;letter-spacing:.15em;'
        f'color:rgba(240,237,232,.22);z-index:999;">round {rnd} · 3</div>',
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 10, 1])
    with col:
        st.markdown('<div style="padding-top:8vh;padding-bottom:4vh;">', unsafe_allow_html=True)

        _inspire_header("aesthetic · selection")

        st.markdown(
            f'<p style="font-family:\'DM Serif Display\',serif;font-style:italic;'
            f'font-size:clamp(18px,2.5vw,30px);color:rgba(240,237,232,.7);'
            f'text-align:center;margin:0 0 40px;">'
            f'which of these feel like you?</p>',
            unsafe_allow_html=True,
        )

        if not urls:
            # Unsplash unavailable — skip
            st.markdown(
                '<p style="text-align:center;color:rgba(240,237,232,.3);'
                'font-family:DM Mono,monospace;font-size:11px;'
                'letter-spacing:.2em;">no images available — add UNSPLASH_ACCESS_KEY to .env</p>',
                unsafe_allow_html=True,
            )
            if st.button("continue →"):
                st.session_state[store_key] = []
                st.session_state.inspire_stage = next_stage
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            return

        # image grid
        grid_cols = st.columns(n_cols, gap="small")
        for i, (url, desc) in enumerate(zip(urls, descs)):
            with grid_cols[i % n_cols]:
                try:
                    st.image(url, use_container_width=True)
                except Exception:
                    st.markdown(
                        f'<div style="height:140px;background:rgba(240,237,232,.04);'
                        f'display:flex;align-items:center;justify-content:center;">'
                        f'<span style="color:rgba(240,237,232,.15);font-size:11px;">image unavailable</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                st.checkbox("select", key=f"{prefix}_{i}", label_visibility="visible")

        # selection count + advance button
        picks_i = _picks_from_ss(prefix, n)
        n_sel   = len(picks_i)
        verb    = "continue →" if rnd < 3 else "build my moodboard →"

        st.markdown(
            f'<p style="font-family:DM Mono,monospace;font-size:9px;'
            f'letter-spacing:.2em;color:rgba(240,237,232,.3);'
            f'text-align:center;margin:24px 0 0;">'
            f'{n_sel} selected · pick at least {min_picks}</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="display:flex;justify-content:center;margin-top:4px;">',
            unsafe_allow_html=True,
        )
        if st.button(verb, disabled=(n_sel < min_picks)):
            picked_urls = [urls[i] for i in picks_i]
            _clear_checks(prefix, n)
            st.session_state[store_key] = picked_urls
            st.session_state.inspire_stage = next_stage
            st.rerun()
        st.markdown("</div></div>", unsafe_allow_html=True)


# ── Inspire stage: moodboard display + approve ───────────────────────────────
def _inspire_moodboard():
    final_picks = (
        st.session_state.inspire_final_picks
        or st.session_state.inspire_r2_picks
        or st.session_state.inspire_r1_picks
    )
    b64s     = st.session_state.inspire_b64s
    analysis = st.session_state.inspire_analysis

    _, col, _ = st.columns([1, 4, 1])
    with col:
        st.markdown('<div style="padding-top:8vh;">', unsafe_allow_html=True)
        _inspire_header("your moodboard")

        # show final images (Unsplash picks or uploaded originals)
        if final_picks:
            img_cols = st.columns(min(len(final_picks), 3), gap="small")
            for i, url in enumerate(final_picks):
                with img_cols[i % 3]:
                    try:
                        st.image(url, use_container_width=True)
                    except Exception:
                        pass
        elif b64s:
            # no Unsplash → show uploaded images
            img_cols = st.columns(min(len(b64s), 3), gap="small")
            for i, b64 in enumerate(b64s):
                with img_cols[i % 3]:
                    st.image(f"data:image/jpeg;base64,{b64}", use_container_width=True)
        else:
            st.markdown(
                '<p style="font-family:\'DM Serif Display\',serif;font-style:italic;'
                'font-size:18px;color:rgba(240,237,232,.25);text-align:center;">'
                'Your aesthetic lives in description — no images, but the feeling is clear.</p>',
                unsafe_allow_html=True,
            )

        # VLM aesthetic summary
        if analysis:
            st.markdown(
                f'<div style="margin:40px 0 32px;padding:28px 32px;'
                f'border-left:1px solid rgba(240,237,232,.1);">'
                f'<p style="font-family:DM Mono,monospace;font-size:9px;'
                f'letter-spacing:.25em;text-transform:uppercase;'
                f'color:rgba(240,237,232,.22);margin:0 0 12px;">aesthetic · reading</p>'
                f'<p style="font-family:\'DM Serif Display\',serif;font-style:italic;'
                f'font-size:16px;line-height:1.7;color:rgba(240,237,232,.65);">'
                f'{analysis}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # approve button
        st.markdown(
            '<div style="text-align:center;margin:16px 0 80px;">',
            unsafe_allow_html=True,
        )
        if st.button("this is my aesthetic →"):
            _inspire_approve(final_picks, b64s, analysis)
        st.markdown("</div></div>", unsafe_allow_html=True)


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
        _inspire_grid(
            rnd=1, urls=st.session_state.inspire_r1_urls,
            descs=st.session_state.inspire_r1_descs,
            n_cols=4, min_picks=2, next_stage="r1_to_r2", store_key="inspire_r1_picks",
        )

    elif stage == "r1_to_r2":
        # Describe what round 1 picks suggest so queries can be refined
        picks = st.session_state.inspire_r1_picks
        pick_descs = st.session_state.inspire_r1_descs
        # Build description from descriptions of selected images
        selected_descs = [
            d for url, d in zip(st.session_state.inspire_r1_urls, pick_descs)
            if url in picks
        ]
        refine_desc = "; ".join(selected_descs[:4]) if selected_descs else ""
        _inspire_preparing(next_stage="r2_show", refine_desc=refine_desc)

    elif stage == "r2_show":
        _inspire_grid(
            rnd=2, urls=st.session_state.inspire_r2_urls,
            descs=st.session_state.inspire_r2_descs,
            n_cols=4, min_picks=2, next_stage="r2_to_r3", store_key="inspire_r2_picks",
        )

    elif stage == "r2_to_r3":
        picks = st.session_state.inspire_r2_picks
        pick_descs = st.session_state.inspire_r2_descs
        selected_descs = [
            d for url, d in zip(st.session_state.inspire_r2_urls, pick_descs)
            if url in picks
        ]
        refine_desc = "; ".join(selected_descs[:3]) if selected_descs else ""
        _inspire_preparing(next_stage="r3_show", refine_desc=refine_desc)

    elif stage == "r3_show":
        _inspire_grid(
            rnd=3, urls=st.session_state.inspire_r3_urls,
            descs=st.session_state.inspire_r3_descs,
            n_cols=3, min_picks=2, next_stage="moodboard", store_key="inspire_final_picks",
        )

    elif stage == "moodboard":
        _inspire_moodboard()


# ─────────────────────────────────────────────────────────────────────────────
# SCREEN ROUTING
# ─────────────────────────────────────────────────────────────────────────────
def _screen() -> str:
    s = st.session_state.agent_session
    if s.get("onboarding_complete"):  return "analysis"
    if s.get("quiz_complete"):        return "inspire"
    return "quiz"


# ─────────────────────────────────────────────────────────────────────────────
# SCREEN 1 — QUIZ
# ─────────────────────────────────────────────────────────────────────────────
def _quiz():
    sess = st.session_state.agent_session
    step = sess.get("quiz_step", 0)

    last = next(
        (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "sensi"),
        "Hi.",
    )

    st.markdown(
        f'<div style="position:fixed;top:28px;right:40px;'
        f'font-family:DM Mono,monospace;font-size:10px;letter-spacing:.15em;'
        f'color:rgba(240,237,232,.22);z-index:999;">{step} · 6</div>',
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div style="padding-top:16vh;"></div>', unsafe_allow_html=True)

        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:center;'
            f'gap:10px;margin-bottom:72px;">'
            f'{_LOGO_SVG}'
            f'<span style="font-family:DM Mono,monospace;font-size:10px;'
            f'letter-spacing:.32em;color:rgba(240,237,232,.20);'
            f'text-transform:uppercase;">sensi</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<p class="fade-up" style="font-family:\'DM Serif Display\',serif;'
            f'font-size:clamp(20px,3vw,36px);line-height:1.4;color:#F0EDE8;'
            f'text-align:center;margin:0 0 56px;">{last}</p>',
            unsafe_allow_html=True,
        )

        submitted, user_input = False, ""
        with st.form("quiz_form", clear_on_submit=True):
            user_input = st.text_input(
                "answer", placeholder="your answer", label_visibility="hidden",
            )
            submitted = st.form_submit_button("continue →")

        st.markdown('<div style="padding-bottom:18vh;"></div>', unsafe_allow_html=True)

    if submitted and user_input.strip():
        st.session_state.messages.append({"role": "user",  "content": user_input.strip()})
        resp = _run(user_input.strip(), context="quiz")
        st.session_state.messages.append({"role": "sensi", "content": resp})
        st.rerun()


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
                        f'<div class="fade-up" style="'
                        f'font-family:\'DM Serif Display\',serif;'
                        f'font-style:italic;font-size:17px;line-height:1.78;'
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
                '<p style="font-family:\'DM Serif Display\',serif;'
                'font-style:italic;font-size:19px;line-height:1.65;'
                'color:rgba(240,237,232,.10);margin-top:40px;">'
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


# ── main ──────────────────────────────────────────────────────────────────────
screen = _screen()
if   screen == "quiz":    _quiz()
elif screen == "inspire": _inspire()
else:                     _analysis()
