# Team 04 — TerraPilot Implementation Progress

_Last updated: 2026-05-03_

---

## Status Summary

| Area | Status | Notes |
|---|---|---|
| LangGraph workflow | ✅ Done | Phase-aware 3-node graph with auto-evaluate gate |
| System prompt | ✅ Done | Full TerraPilot philosophy + 23 tools in `reason.py` |
| Tool definitions | ✅ Done | 21 GH tools + 2 LLM-side tools documented |
| Mock MCP client | ✅ Done | All 21 stubs returning realistic JSON |
| Notebook explorer | ✅ Done | 19-cell notebook, all sections running |
| LLM configuration | ✅ Done | Cloudflare Workers AI working (`google/gemini-3.1-flash-lite`) |
| Graph visualization | ✅ Done | LangGraph PNG + matplotlib workflow diagram |
| Grasshopper tools | 🔄 In progress | GH clusters started; tool definitions documented |
| End-to-end agent run | 🔄 In progress | Runs with mocks; needs live GH connection |
| Test cases | 📋 Planned | 5 scenarios defined; validation pending |

---

## Completed Work

### 1. LangGraph Workflow Redesign (`graph.py`)

Replaced the original 2-node reason/tool loop with a **3-node phase-aware graph**:

```
START → reason ──(tool calls)──────────────────────► tool ──► reason
               └──(final + geometry + !evaluated)──► auto_evaluate ──► reason
               └──(final + evaluated / no geometry)─────────────────► END
```

**New nodes:**
- `reason` — LLM decides: call tools, finish, or both
- `tool` — MCP tool execution, auto-extracts `geometry_id` from `parametric_shape_generator_04` responses
- `auto_evaluate` — fires automatically once per geometry; calls all 3 evaluators sequentially, then clears `final_response` so the LLM synthesises a qualified response

**New `AgentState` fields:**
| Field | Type | Purpose |
|---|---|---|
| `phase` | `str` | `"design"` \| `"evaluate"` \| `"done"` |
| `geometry_id` | `str \| None` | Active parametric geometry ID — auto-extracted |
| `evaluation_done` | `bool` | Gate: `True` after `auto_evaluate` has run |

**Routing logic (`_route`):**
1. If `final_response` is set AND `geometry_id` exists AND `evaluation_done=False` → `"evaluate"`
2. If `final_response` is set AND (no geometry OR already evaluated) → `"finish"`
3. If `iteration >= max_iterations` → `"finish"`
4. Otherwise → `"run_tool"`

---

### 2. System Prompt (`nodes/reason.py`)

Updated `SYSTEM_PROMPT` with:
- TerraPilot design philosophy (site-reading → shape → constraints → manipulation → evaluate)
- All 23 tools listed with usage guidance
- Explicit instruction to always run evaluators before concluding
- Phase-aware instructions for each workflow stage

---

### 3. Tool Catalog (21 MCP tools + 2 LLM-side)

**Site Input (2):** `site_boundary_reader_04`, `context_reader_04`

**Shape Design (3):** `shape_library_loader_04`, `legal_constraints_reader_04`, `parametric_shape_generator_04`

**Constraint Checking (5):** `site_fit_checker_04`, `setback_checker_04`, `area_requirement_checker_04`, `adjacency_access_checker_04`, `tree_constraint_checker_04`

**Manipulation (7):** `scale_shape_tool_04`, `stretch_arm_tool_04`, `width_modifier_tool_04`, `courtyard_modifier_tool_04`, `rotate_mirror_tool_04`, `bend_angle_tool_04`, `terrace_step_tool_04`

**Evaluation — auto-forced (3):** `spatial_intention_evaluator_04`, `performance_evaluator_04`, `shape_integrity_evaluator_04`

**Output (1):** `bake_geometry_id_04`

**LLM-side (2):** `why_operation_selector_04`, `explain_decision_tool_04`

---

### 4. Notebook Explorer (`terrapilot_explore.ipynb`)

19-cell interactive notebook — all sections functional:

| Cell | Section | Status |
|---|---|---|
| 1–2 | Title + TOC | ✅ |
| 3 | Setup & `sys.path` | ✅ |
| 4–6 | LLM config override (Cloudflare) | ✅ |
| 7–10 | Mock MCP client + 21 tool stubs | ✅ |
| 11–12 | Tool catalog review | ✅ |
| 13–15 | Graph visualization (LangGraph PNG + matplotlib workflow) | ✅ |
| 16–17 | 5 test case definitions | ✅ |
| 18–19 | Full agent run (requires valid API call) | 🔄 |

**Visualization outputs:**
- `terrapilot_workflow.png` — 5-column swimlane diagram of all 21 tools by phase

---

### 5. Environment & Dependencies

- **Python env:** conda `311` (Python 3.11.13)
- **Installed packages:** `langgraph`, `langchain_openai`, `grandalf`, `matplotlib`, `httpx`, `python-dotenv`
- **LLM provider:** Cloudflare Workers AI — `google/gemini-3.1-flash-lite`
- **Config file:** `.env` at repo root (AIA26_Studio)

---

## In Progress

### Grasshopper Tool Implementation

GH clusters started. Tool definitions written for the first 5 tools:
- `site_boundary_reader_04` — site polygon → boundary curve + area metrics
- `context_reader_04` — roads, buildings, entrances → baked context geometry
- `parametric_shape_generator_04` — returns a live-editable geometry with `geometry_id`

Still needed (16 remaining GH tools):
- All constraint checkers (5)
- All manipulation tools (7)
- All evaluators (3)
- `bake_geometry_id_04`

---

## Next Steps

### Priority 1 — Fix `run_agent` stale `print_ascii` call
`graph.py` `run_agent` still has a stale `print_ascii()` call that should be removed (it will fail at runtime):
```python
# Remove these two lines in run_agent:
print("\nWorkflow graph:")
app.get_graph().print_ascii()
```

### Priority 2 — Validate end-to-end agent run (cell 19)
Run the full agent with mock stubs to confirm the 3-node flow executes correctly — especially:
- `auto_evaluate` fires when `geometry_id` is present
- LLM synthesises evaluation results before returning

### Priority 3 — Grasshopper tool implementation
Build GH components for the 16 remaining tools. Each tool needs:
1. GH cluster (input/output wires)
2. MCP registration in `mcp.json`
3. Stub updated to match real output schema

### Priority 4 — Test case validation
Run each of the 5 test cases (`simple_bar`, `pentagon_trees`, `sloped_site`, `gfa_deficit`, `irregular_boundary`) against the live graph.

---

## Known Issues

| Issue | Severity | Status |
|---|---|---|
| `print_ascii()` in `run_agent` | Low | Open — cosmetic, won't crash if grandalf is installed |
| Cell 19 hits `max_iterations` (6) before completing full workflow | Medium | Under investigation — may need to raise to 12–15 for complex prompts |
| Cloudflare model may not support tool-use reliably | Medium | Monitor — may need to switch to `@cf/meta/llama-3.3-70b-instruct-fp8-fast` |
