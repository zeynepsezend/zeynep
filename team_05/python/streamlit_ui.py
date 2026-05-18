"""
AIA Studio Cost Advisor — Team 05
Streamlit GUI: interactive floor-plan cost heatmap + agent chat.

Run with:  streamlit run streamlit_ui.py
Requires:  streamlit>=1.33, plotly, pandas
"""
import copy
import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from langgraph_agent import LangGraphAgent

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AIA Cost Advisor — Team 05",
    page_icon="🏗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* main background white, text dark */
.stApp { background: #ffffff; color: #1a1a1a; }
section[data-testid="stSidebar"] { background: #f0f0f0; border-right: 1px solid #ddd; }
/* sidebar text */
section[data-testid="stSidebar"] * { color: #222 !important; }
/* headings */
h1, h2, h3, h4, h5 { color: #111 !important; }
/* metric labels and values */
[data-testid="stMetricLabel"] { color: #555 !important; }
[data-testid="stMetricValue"] { color: #111 !important; }
/* divider */
hr { border-color: #ddd; }
/* room card */
.room-card { background: #f7f7f7; border: 1px solid #ddd;
             border-radius: 10px; padding: 0.85rem 1rem; margin-top: 0.5rem; }
.room-card h4 { margin: 0 0 0.5rem 0; color: #1a1a1a; }
.kv-row { display: flex; justify-content: space-between;
          border-bottom: 1px solid #e5e5e5; padding: 0.2rem 0; font-size: 0.88rem; }
.kv-key { color: #666; }
.kv-val { color: #111; font-weight: 600; }
/* caption / small text */
.stCaption, small { color: #666 !important; }
</style>
""", unsafe_allow_html=True)

# ── session state ─────────────────────────────────────────────────────────────
for _k, _v in {
    "layout": None,
    "messages": [],
    "selected_room": None,
    "pending_prompt": "",
    "agent": LangGraphAgent(),
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── helpers ───────────────────────────────────────────────────────────────────

def _merge_gh_colors(base: dict, gh: dict) -> dict:
    """
    Overlay updated color_hex / heat_t / total_cost / rate_per_m2 from gh onto
    the base layout. Matches by id first, then by lowercase name as fallback.
    """
    result = copy.deepcopy(base)
    gh_rooms = gh.get("rooms", [])
    gh_by_id   = {r.get("id"): r for r in gh_rooms}
    gh_by_name = {(r.get("name") or "").lower(): r for r in gh_rooms}
    for room in result.get("rooms", []):
        src = (gh_by_id.get(room.get("id"))
               or gh_by_name.get((room.get("name") or "").lower()))
        if src:
            for key in ("color_hex", "color_rgb", "heat_t", "total_cost", "rate_per_m2"):
                if key in src:
                    room[key] = src[key]
    if "heatmap" in gh:
        result["heatmap"] = gh["heatmap"]
    if "totals" in gh:
        result["totals"] = gh["totals"]
    return result


def _write_gh_file(layout: dict) -> None:
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "team_05_edited_layout.json")
    )
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(layout, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.warning(f"Could not write to GH file: {e}")


# ── colour helpers ────────────────────────────────────────────────────────────
_RAMP = [(255, 255, 224), (255, 200, 0), (255, 120, 0), (189, 0, 38)]

def _lerp_color(t: float) -> str:
    t = max(0.0, min(1.0, t))
    seg = t * (len(_RAMP) - 1)
    lo, hi = int(seg), min(int(seg) + 1, len(_RAMP) - 1)
    f = seg - lo
    r = int(_RAMP[lo][0] + f * (_RAMP[hi][0] - _RAMP[lo][0]))
    g = int(_RAMP[lo][1] + f * (_RAMP[hi][1] - _RAMP[lo][1]))
    b = int(_RAMP[lo][2] + f * (_RAMP[hi][2] - _RAMP[lo][2]))
    return f"rgb({r},{g},{b})"

def _text_on(t: float) -> str:
    return "#111" if t < 0.55 else "#fff"


# ── floor plan ────────────────────────────────────────────────────────────────
def build_floor_plan(layout: dict, selected_id: str | None = None) -> go.Figure:
    rooms    = layout.get("rooms", [])
    openings = layout.get("openings", [])
    columns  = layout.get("columns", [])
    currency = layout.get("project", {}).get("currency", "")

    costs = [r.get("total_cost", 0) for r in rooms]
    mn, mx = (min(costs), max(costs)) if costs else (0, 1)
    span = (mx - mn) or 1

    fig = go.Figure()

    for room in rooms:
        poly = room.get("polygon", [])
        if not poly:
            continue
        xs = [p[0] for p in poly] + [poly[0][0]]
        ys = [p[1] for p in poly] + [poly[0][1]]
        t    = room.get("heat_t", (room.get("total_cost", mn) - mn) / span)
        fill = room.get("color_hex") or _lerp_color(t)
        is_sel = room.get("id") == selected_id
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)

        fig.add_trace(go.Scatter(
            x=xs, y=ys, fill="toself", fillcolor=fill,
            line=dict(color="#60a5fa" if is_sel else "#555", width=3 if is_sel else 1),
            mode="lines", name=room.get("name", ""),
            customdata=[[
                room.get("id", ""), room.get("name", ""),
                room.get("area_m2", 0), room.get("total_cost", 0),
                room.get("rate_per_m2", 0), room.get("category", ""),
            ]],
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                f"Area: %{{customdata[2]:.1f}} m²<br>"
                f"Rate: %{{customdata[4]:,.0f}} {currency}/m²<br>"
                f"<b>Cost: %{{customdata[3]:,.0f}} {currency}</b>"
                "<extra></extra>"
            ),
        ))
        fig.add_annotation(
            x=cx, y=cy,
            text=f"<b>{room.get('name','')}</b><br>{room.get('total_cost',0)/1000:.0f}k {currency}",
            showarrow=False, font=dict(size=9, color=_text_on(t)), align="center",
        )

    for op in (openings + columns):
        poly = op.get("polygon", [])
        if not poly:
            continue
        ox = [p[0] for p in poly] + [poly[0][0]]
        oy = [p[1] for p in poly] + [poly[0][1]]
        op_type = (op.get("type") or op.get("category") or "").lower()
        fill   = op.get("color_hex") or ("rgba(92,45,0,0.85)" if "door" in op_type else
                                          "rgba(30,144,255,0.55)" if "window" in op_type else
                                          "rgba(130,130,130,0.7)")
        border = op.get("color_hex") or ("#3d1a00" if "door" in op_type else
                                          "#0050b3" if "window" in op_type else "#444")
        fig.add_trace(go.Scatter(
            x=ox, y=oy, fill="toself", fillcolor=fill,
            line=dict(color=border, width=1), mode="lines",
            name=op_type.capitalize(), showlegend=False,
            hovertemplate=(
                f"<b>{op_type.capitalize()}</b> ({op.get('subtype','')})<br>"
                f"Cost: {op.get('cost',0):,.0f} {currency}<extra></extra>"
            ),
        ))

    fig.update_layout(
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="#ffffff", plot_bgcolor="#f7f7f7",
        xaxis=dict(showgrid=False, zeroline=False, scaleanchor="y",
                   scaleratio=1, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        clickmode="event+select", dragmode="select",
    )
    return fig


# ── GH legend ────────────────────────────────────────────────────────────────
def build_gh_legend(layout: dict) -> str:
    heatmap  = layout.get("heatmap", {})
    ranges   = heatmap.get("ranges", {})
    ramps    = heatmap.get("ramps", {})
    currency = layout.get("project", {}).get("currency", "")
    _fallback = {
        "rooms":   [("#FFF5DC",0),("#FED976",.25),("#FEB24C",.5),("#F06913",.75),("#BD0026",1)],
        "doors":   [("#E8CDAA",0),("#B27A41",.5),("#643719",1)],
        "windows": [("#D2E8F0",0),("#5AA0CD",.5),("#194B91",1)],
        "columns": [("#C8C8C8",0),("#828282",.5),("#404040",1)],
    }
    blocks = []
    for cat in ("rooms", "doors", "windows", "columns"):
        r = ranges.get(cat, {})
        lo, hi = r.get("min", 0), r.get("max", 0)
        stops = ramps.get(cat, [])
        if stops:
            grad = "linear-gradient(to right," + ",".join(f"{s['hex']} {int(s['t']*100)}%" for s in stops) + ")"
        else:
            grad = "linear-gradient(to right," + ",".join(f"{h} {int(t*100)}%" for h,t in _fallback[cat]) + ")"
        blocks.append(f"""
<div style="margin-bottom:10px">
  <div style="font-size:0.78rem;color:#555;margin-bottom:3px">
    {cat.capitalize()} ({lo:,.0f}–{hi:,.0f} {currency})
  </div>
  <div style="height:14px;border-radius:4px;background:{grad};border:1px solid #ccc"></div>
  <div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#888;margin-top:2px">
    <span>{lo:,.0f}</span><span>{hi:,.0f}</span>
  </div>
</div>""")
    return "\n".join(blocks)


# ── cost table ────────────────────────────────────────────────────────────────
def build_cost_df(layout: dict) -> pd.DataFrame:
    currency = layout.get("project", {}).get("currency", "")
    rows = [{"Room": r.get("name",""), "Category": r.get("category","").capitalize(),
             "Area (m²)": round(r.get("area_m2",0),1),
             f"Rate ({currency}/m²)": int(r.get("rate_per_m2",0)),
             f"Cost ({currency})": int(r.get("total_cost",0))}
            for r in layout.get("rooms", [])]
    df = pd.DataFrame(rows)
    if not df.empty:
        currency = layout.get("project", {}).get("currency", "")
        totals = {"Room":"TOTAL","Category":"","Area (m²)":df["Area (m²)"].sum(),
                  f"Rate ({currency}/m²)":0,
                  f"Cost ({currency})":df[f"Cost ({currency})"].sum()}
        df = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
    return df


# ── room card ─────────────────────────────────────────────────────────────────
def render_room_card(room: dict, currency: str) -> None:
    def kv(k, v):
        return f'<div class="kv-row"><span class="kv-key">{k}</span><span class="kv-val">{v}</span></div>'
    html = (f'<div class="room-card"><h4>{room.get("name","")}</h4>'
            + kv("Category", room.get("category","").capitalize())
            + kv("Area", f'{room.get("area_m2",0):.1f} m²')
            + kv("Rate", f'{room.get("rate_per_m2",0):,.0f} {currency}/m²')
            + kv("Total cost", f'<span style="color:#86efac">{room.get("total_cost",0):,.0f} {currency}</span>')
            + "</div>")
    st.markdown(html, unsafe_allow_html=True)


# ── chat ──────────────────────────────────────────────────────────────────────
def render_chat() -> None:
    for msg in st.session_state.messages:
        role = "user" if msg["role"] == "user" else "assistant"
        with st.chat_message(role):
            st.markdown(msg["content"])


# =============================================================================
# SIDEBAR — layout upload is the ONLY source of truth for the layout
# =============================================================================
with st.sidebar:
    st.markdown("### Load Layout")
    st.caption("Upload your layout JSON — this is the only way to change the floor plan.")
    uploaded = st.file_uploader("Layout JSON", type=["json"], label_visibility="collapsed")
    if uploaded:
        # Only reload when a NEW file is chosen — not on every rerun
        if st.session_state.get("_upload_id") != uploaded.file_id:
            st.session_state.layout = json.load(uploaded)
            st.session_state._upload_id = uploaded.file_id
            st.session_state.selected_room = None
            st.success("Layout loaded.")

    if st.session_state.layout:
        proj     = st.session_state.layout.get("project", {})
        rooms    = st.session_state.layout.get("rooms", [])
        currency = proj.get("currency", "")
        totals   = st.session_state.layout.get("totals", {})
        room_total = totals.get("rooms", sum(r.get("total_cost",0) for r in rooms))
        grand      = totals.get("grand", room_total)

        st.markdown(f"**{proj.get('name','')}**")
        c1, c2 = st.columns(2)
        c1.metric("Rooms", len(rooms))
        c2.metric("Footprint", f"{proj.get('footprint_m2',0):.0f} m²")
        st.metric("Room construction", f"{room_total:,.0f} {currency}")
        if grand != room_total:
            st.metric("Grand total", f"{grand:,.0f} {currency}")

        st.divider()
        st.markdown("### Grasshopper")
        if st.button("Check connection", use_container_width=True):
            from swiftlet_mcp import check_connection
            ok, info = check_connection()
            if ok:
                st.success(f"Connected — {len(info.split(','))} tools")
            else:
                st.error(f"Not reachable: {info[:80]}")

        st.divider()
        st.markdown("### Quick Prompts")
        for qp in [
            "What is the total project cost?",
            "Which room is most expensive?",
            "Which room has the highest rate per m²?",
            "How can I reduce the bathroom cost?",
            "Compare the living room and master bedroom",
        ]:
            if st.button(qp, key=f"qp_{qp[:18]}", use_container_width=True):
                st.session_state.pending_prompt = qp
                st.rerun()
    else:
        st.info("Upload a layout JSON to begin.")


# =============================================================================
# MAIN — floor plan (left) + chat (right)
# =============================================================================
st.markdown("## AIA Studio · Cost Advisor · Team 05")
st.caption("Upload a layout JSON in the sidebar · Click a room to inspect · Ask the agent questions")
st.divider()

col_plan, col_chat = st.columns([3, 2], gap="large")

# ─────────────────────────── FLOOR PLAN ──────────────────────────────────────
with col_plan:
    if st.session_state.layout:
        st.markdown("#### Floor Plan — Cost Heatmap")
        st.caption("Colors from Grasshopper. Click a room to select it.")

        sel_id = (st.session_state.selected_room or {}).get("id")
        fig    = build_floor_plan(st.session_state.layout, sel_id)

        plan_col, legend_col = st.columns([5, 1], gap="small")

        with legend_col:
            st.markdown(
                '<div style="padding-top:2.5rem">'
                + build_gh_legend(st.session_state.layout)
                + "</div>",
                unsafe_allow_html=True,
            )

        with plan_col:
            try:
                event = st.plotly_chart(
                    fig, use_container_width=True,
                    on_select="rerun", key="floor_plan_chart",
                )
                if event:
                    pts = (event.get("selection") or {}).get("points", [])
                    if pts:
                        cd = pts[0].get("customdata", [])
                        if cd:
                            room_id   = cd[0]
                            all_rooms = st.session_state.layout.get("rooms", [])
                            match     = next((r for r in all_rooms if r.get("id") == room_id), None)
                            if match:
                                st.session_state.selected_room = match
            except TypeError:
                st.plotly_chart(fig, use_container_width=True)

        # selected room card
        if st.session_state.selected_room:
            room     = st.session_state.selected_room
            currency = st.session_state.layout.get("project", {}).get("currency", "")
            render_room_card(room, currency)
            ask_col, clr_col = st.columns([3, 1])
            if ask_col.button("Ask agent about this room", use_container_width=True):
                st.session_state.pending_prompt = (
                    f"Analyse the cost of the {room.get('name')} "
                    f"({room.get('area_m2',0):.1f} m² at "
                    f"{room.get('rate_per_m2',0):,.0f} {currency}/m²). "
                    "How does it compare to similar rooms and how could it be reduced?"
                )
                st.rerun()
            if clr_col.button("Deselect", use_container_width=True):
                st.session_state.selected_room = None
                st.rerun()

        # cost table
        with st.expander("Cost Breakdown Table", expanded=False):
            df       = build_cost_df(st.session_state.layout)
            currency = st.session_state.layout.get("project", {}).get("currency", "")
            fmt      = {f"Rate ({currency}/m²)": "{:,.0f}",
                        f"Cost ({currency})": "{:,.0f}", "Area (m²)": "{:.1f}"}

            def _hl(row):
                return (["font-weight:bold;background:#1e3a5f"] * len(row)
                        if row["Room"] == "TOTAL" else [""] * len(row))

            st.dataframe(df.style.apply(_hl, axis=1).format(fmt),
                         use_container_width=True, hide_index=True)
    else:
        st.markdown("#### Floor Plan")
        st.info("Upload a **layout JSON** in the sidebar to see the interactive floor plan.")

# ────────────────────────────── CHAT ─────────────────────────────────────────
with col_chat:
    st.markdown("#### Agent Chat")

    chat_area = st.container(height=400)
    with chat_area:
        if st.session_state.messages:
            render_chat()
        else:
            st.caption("Ask a question or click a room to start.")

    pending = st.session_state.pop("pending_prompt", "") \
              if "pending_prompt" in st.session_state else ""

    user_text = st.chat_input(
        placeholder='e.g. "bedroom 3 floor finish marble" or "total cost?"',
        key="chat_input",
    )

    if pending and not user_text:
        user_text = pending

    if user_text and user_text.strip():
        st.session_state.messages.append({"role": "user", "content": user_text.strip()})
        with chat_area:
            with st.chat_message("user"):
                st.markdown(user_text.strip())
            with st.chat_message("assistant"):
                placeholder = st.empty()
                placeholder.markdown("_Thinking..._")
        reply = None
        gh_synced = False
        try:
            reply = st.session_state.agent.process(
                user_text.strip(),
                layout=st.session_state.layout,
                history=st.session_state.messages[:-1],
            )
            updated = st.session_state.agent.get_updated_layout()
            if updated is not None and st.session_state.layout is not None:
                st.session_state.layout = _merge_gh_colors(
                    st.session_state.layout, updated
                )
                st.session_state.selected_room = None
                _write_gh_file(st.session_state.layout)
                gh_synced = True
        except Exception as exc:
            reply = f"Agent error: {exc}"
        finally:
            if reply is not None:
                placeholder.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
        if gh_synced:
            st.toast("Heatmap & Grasshopper synced", icon="✅")
        st.rerun()

    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ── cost pie charts (full-width row below both columns) ───────────────────────
if st.session_state.layout:
    _layout   = st.session_state.layout
    _currency = _layout.get("project", {}).get("currency", "")
    _rooms    = _layout.get("rooms", [])
    _openings = _layout.get("openings", [])
    _cols     = _layout.get("columns", [])
    _doors    = [o for o in _openings if (o.get("type") or "").lower() == "door"]
    _windows  = [o for o in _openings if (o.get("type") or "").lower() == "window"]

    st.divider()
    st.markdown("#### Cost Breakdown")

    pie_r, pie_d, pie_w, pie_c = st.columns(4, gap="large")

    def _pie_legend(labels, colors):
        items = "".join(
            f'<div style="display:flex;align-items:center;gap:5px;margin-bottom:3px">'
            f'<div style="width:10px;height:10px;border-radius:2px;background:{c};flex-shrink:0"></div>'
            f'<span style="font-size:11px;color:#444;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{l}</span>'
            f'</div>'
            for l, c in zip(labels, colors)
        )
        return f'<div style="padding-top:4px">{items}</div>'

    _PIE_LAYOUT = dict(
        margin=dict(l=5, r=5, t=30, b=5),
        paper_bgcolor="#ffffff",
        showlegend=False,
        height=220,
    )

    with pie_r:
        if _rooms:
            labels = [r.get("name", "") for r in _rooms]
            values = [r.get("total_cost", 0) or 0 for r in _rooms]
            colors = [r.get("color_hex") or "#FEB24C" for r in _rooms]
            fig_r = go.Figure(go.Pie(
                labels=labels, values=values,
                marker=dict(colors=colors, line=dict(color="#fff", width=1)),
                textinfo="percent",
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} " + _currency + "<extra></extra>",
                hole=0.4,
            ))
            fig_r.update_layout(title=dict(text="Rooms", font=dict(size=13, color="#333"), x=0.5), **_PIE_LAYOUT)
            st.plotly_chart(fig_r, use_container_width=True)
            st.markdown(_pie_legend(labels, colors), unsafe_allow_html=True)

    with pie_d:
        if _doors:
            d_labels = [d.get("subtype") or d.get("id") or "Door" for d in _doors]
            d_values = [d.get("cost", 0) or 0 for d in _doors]
            d_colors = [d.get("color_hex") or "#B27A41" for d in _doors]
            fig_d = go.Figure(go.Pie(
                labels=d_labels, values=d_values,
                marker=dict(colors=d_colors, line=dict(color="#fff", width=1)),
                textinfo="percent",
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} " + _currency + "<extra></extra>",
                hole=0.4,
            ))
            fig_d.update_layout(title=dict(text="Doors", font=dict(size=13, color="#333"), x=0.5), **_PIE_LAYOUT)
            st.plotly_chart(fig_d, use_container_width=True)
            st.markdown(_pie_legend(d_labels, d_colors), unsafe_allow_html=True)
        else:
            st.caption("No door data")

    with pie_w:
        if _windows:
            w_labels = [w.get("subtype") or w.get("id") or "Window" for w in _windows]
            w_values = [w.get("cost", 0) or 0 for w in _windows]
            w_colors = [w.get("color_hex") or "#5AA0CD" for w in _windows]
            fig_w = go.Figure(go.Pie(
                labels=w_labels, values=w_values,
                marker=dict(colors=w_colors, line=dict(color="#fff", width=1)),
                textinfo="percent",
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} " + _currency + "<extra></extra>",
                hole=0.4,
            ))
            fig_w.update_layout(title=dict(text="Windows", font=dict(size=13, color="#333"), x=0.5), **_PIE_LAYOUT)
            st.plotly_chart(fig_w, use_container_width=True)
            st.markdown(_pie_legend(w_labels, w_colors), unsafe_allow_html=True)
        else:
            st.caption("No window data")

    with pie_c:
        if _cols:
            c_labels = [c.get("subtype") or c.get("id") or "Column" for c in _cols]
            c_values = [c.get("cost", 0) or 0 for c in _cols]
            c_colors = [c.get("color_hex") or "#828282" for c in _cols]
            fig_c = go.Figure(go.Pie(
                labels=c_labels, values=c_values,
                marker=dict(colors=c_colors, line=dict(color="#fff", width=1)),
                textinfo="percent",
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} " + _currency + "<extra></extra>",
                hole=0.4,
            ))
            fig_c.update_layout(title=dict(text="Columns", font=dict(size=13, color="#333"), x=0.5), **_PIE_LAYOUT)
            st.plotly_chart(fig_c, use_container_width=True)
            st.markdown(_pie_legend(c_labels, c_colors), unsafe_allow_html=True)
        else:
            st.caption("No column data")
