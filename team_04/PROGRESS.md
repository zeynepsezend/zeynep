# Team 04 — TerraPilot Implementation Progress

_Last updated: 2026-05-09_

---

## Status Summary

| Area | Status | Notes |
|---|---|---|
| LangGraph workflow | ✅ Done | Phase-aware 3-node graph with auto-evaluate gate |
| System prompt | ✅ Done | Full TerraPilot philosophy + 23 tools in `reason.py` |
| Tool definitions | ✅ Done | 21 GH tools + 2 LLM-side tools documented |
| Mock MCP client | ✅ Done | All 21 stubs returning realistic JSON |
| Notebook explorer | ✅ Done | 19-cell notebook, all sections running |
| LLM configuration | ✅ Done | Cloudflare Workers AI — `@cf/meta/llama-3.3-70b-instruct-fp8-fast` |
| Graph visualization | ✅ Done | LangGraph PNG + matplotlib workflow diagram |
| End-to-end agent run | ✅ Done | Cell 19 runs successfully with mock stubs |
| `.env` setup | ✅ Done | Credentials file created at repo root |
| API schema fix | ✅ Done | Removed `json_schema` response_format; no timeout/token errors |
| Edited layout output | ✅ Done | `team_04_edited_layout.json` generated from first agent run |
| Documentation suite | ✅ Done | TERRAPILOT_PLAN.md, TOOLS_CHECKLIST.md, QUICK_START.md, README_DELIVERABLES.md |
| GH tool specs | ✅ Done | 2 of 23 detailed specs written: tool 1 (`site_boundary_reader`) + tool 5 (`parametric_shape_generator`) |
| GH cluster parameters | ✅ Done | `team_04_definition_cluster.ghcluster` + working.gh parameter-tuned and verified |
| Grasshopper tools (remaining) | 🔄 In progress | 21 tools still need GH implementation; stubs exist for all |
| Test cases | 🔄 In progress | 2/5 written: `simple_rectangle`, `pentagon_with_trees`; 3 pending |

---

## Bugs Fixed (2026-05-04)

Five root-cause issues were diagnosed and resolved to make the full agent run (cell 19) complete successfully end-to-end.

### Bug 1 — 404 NotFoundError (missing `.env`)
**Symptom:** Cloudflare API returned 404; URL was `/accounts//ai/v1` (empty account ID).  
**Root cause:** `.env` file did not exist at the repo root; `CF_ACCOUNT_ID` was never loaded.  
**Fix:** Created `.env` at `AIA26_Studio/.env` with real Cloudflare credentials.

### Bug 2 — Wrong model name format
**Symptom:** API returned 404 for the model endpoint.  
**Root cause:** `.env` had `"openai/gpt-5.5-pro"`, which is not a valid Cloudflare model identifier.  
**Fix:** Changed `CF_MODEL` to `"@cf/qwen/qwen3-30b-a3b-fp8"` (Cloudflare format uses `@cf/...` prefix).

### Bug 3 — `ImportError: grandalf` in `graph.py`
**Symptom:** `run_agent` crashed after the LangGraph run with `ImportError: No module named 'grandalf'`.  
**Root cause:** `app.get_graph().print_ascii()` was called unconditionally; `grandalf` is not installed.  
**Fix:** Wrapped the call in `try/except ImportError` — graph ASCII is printed only when the package is available.

### Bug 4 — `LengthFinishReasonError` (2 000-token output cap)
**Symptom:** Cloudflare returned a truncated response; `openai` SDK raised `LengthFinishReasonError: completion_tokens=2000`.  
**Root cause:** Cloudflare's default output cap is 2 000 tokens. The LLM needed to emit a full JSON object with tool call arguments but was cut off mid-response.  
**Fix:** Added `max_tokens=8192` to `create_chat_llm()` in `_runtime/llm.py`.

### Bug 5 — `json_schema` response_format caused inference timeouts
**Symptom:** Even after the token-cap fix, every API call timed out (HTTP 408 from Cloudflare) on the first reasoning step.  
**Root cause (double):**
1. `get_llm_response_format()` merged ALL 21 tool input-schema properties into a single combined `json_schema` and sent it with every request (~1 000 extra tokens of schema per call).
2. `"strict": True` forces the model to enumerate every property (even null ones) in the output, multiplying response size.
3. The Qwen 30B model is too slow to handle this load within Cloudflare's inference timeout budget.

**Fix (three-part):**
- Changed `get_llm_response_format()` to return `{}` — no `response_format` sent to the API.
- Switched model to `@cf/meta/llama-3.3-70b-instruct-fp8-fast` in `.env` (faster FP8 variant).
- Increased `timeout_seconds` to 300 and `max_iterations` to 20 in cell 19.

### Bug 6 — Stale Python module cache in Jupyter kernel
**Symptom:** File edits to `_runtime/llm.py` and `graph.py` did not take effect — Jupyter kernel served the old cached versions from `sys.modules`.  
**Root cause:** Python caches imported modules; edits to `.py` files are invisible to the running kernel until the module is reloaded or the kernel is restarted.  
**Fix:** Added `importlib.reload()` calls at the top of cell 19 for both `_runtime.llm` and `graph`, so every execution picks up the latest disk versions without a kernel restart.

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

19-cell interactive notebook — **all sections functional and fully tested:**

| Cell | Section | Status |
|---|---|---|
| 1–2 | Title + TOC | ✅ |
| 3 | Setup & `sys.path` | ✅ |
| 4–6 | LLM config override (Cloudflare) | ✅ |
| 7–10 | Mock MCP client + 21 tool stubs | ✅ |
| 11–12 | Tool catalog review | ✅ |
| 13–15 | Graph visualization (LangGraph PNG + matplotlib workflow) | ✅ |
| 16–17 | 5 test case definitions | ✅ |
| 18–19 | **Full agent run — runs successfully end-to-end** | ✅ **Done** |

**Cell 19 specifics — what changed:**
- `importlib.reload(_runtime.llm)` and `importlib.reload(graph)` at cell top — always picks up latest file edits
- `LLM_OVERRIDE["max_iterations"] = 20` — enough for a complete TerraPilot workflow
- `LLM_OVERRIDE["timeout_seconds"] = 300` — covers multi-turn conversations where history grows
- `build_llm_from_override()` re-called each run — picks up model/credential changes from `.env`

**Visualization outputs:**
- `terrapilot_workflow.png` — 5-column swimlane diagram of all 21 tools by phase

---

### 5. Documentation Suite (Added 2026-05-04)

Four new top-level documentation files were added to `team_04/`:

| File | Purpose |
|---|---|
| `TERRAPILOT_PLAN.md` | Complete implementation plan — full specs for all 23 tools with input/output schemas, GH notes, and a week-by-week timeline |
| `TOOLS_CHECKLIST.md` | Interactive checkbox list for all 23 tools with per-tool sub-tasks and priority levels |
| `QUICK_START.md` | Week-by-week and day-by-day guide for building GH clusters; includes placeholder templates and testing workflow |
| `README_DELIVERABLES.md` | Summary of all deliverables created — intended as a hand-off reference |

---

### 6. Grasshopper Tool Specifications (`gh/tool_definitions/`)

Detailed markdown specs added for 2 priority tools:

| File | Tool | Status |
|---|---|---|
| `01_site_boundary_reader.md` | `site_boundary_reader_04` | ✅ Full spec — inputs, outputs, example JSON, GH steps |
| `05_parametric_shape_generator.md` | `parametric_shape_generator_04` | ✅ Full spec — geometry_id generation, shape types, parameter schema |
| `README.md` | GH cluster template | ✅ Python component templates for JSON parse/format pattern |

Remaining 21 tools: stubs in mock MCP client; specs not yet written.

---

### 7. Grasshopper Cluster Updates

`team_04_definition_cluster.ghcluster` and `team_04_working.gh` were updated (commit `81f342a`):
- Parameters adjusted to ensure tools are wired correctly
- Binary changes only (no new text-visible changes)
- MCP tool registration in `team_04_result_cluster.ghcluster` also updated

---

### 8. Test Cases Written

Two detailed test cases added to `test_cases/`:

| File | Scenario | Contents |
|---|---|---|
| `test_01_simple_rectangle.md` | Simple rectangular site | Site coords, expected tool sequence, pass/fail criteria |
| `test_02_pentagon_with_trees.md` | Irregular pentagon + 3 trees | Tree constraint testing, setback validation, geometry manipulation |

3 remaining planned scenarios (`sloped_site`, `gfa_deficit`, `irregular_boundary`) not yet written.

---

### 9. Edited Layout Output

`team_04_edited_layout.json` was generated from the first successful end-to-end agent run and committed to the repo. It serves as the baseline for subsequent test runs.

---

### 5. Environment & Dependencies

- **Python env:** Python 3.14.4 kernel
- **Installed packages:** `langgraph`, `langchain_openai`, `matplotlib`, `httpx`, `python-dotenv`  
  Note: `grandalf` is optional — used for `print_ascii()` only; absence is handled gracefully
- **LLM provider:** Cloudflare Workers AI — `@cf/meta/llama-3.3-70b-instruct-fp8-fast`
- **Config file:** `.env` at repo root (`AIA26_Studio/.env`) — must contain `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `CF_MODEL`

---

## In Progress

### Grasshopper Tool Implementation

GH clusters have been started and parameters tuned. Detailed specs exist for tools 1 and 5. Still needed:

| Category | Tools | Count |
|---|---|---|
| Input | `context_reader_04` | 1 |
| Shape | `shape_library_loader_04`, `legal_constraints_reader_04` | 2 |
| Constraint | `site_fit_checker_04`, `setback_checker_04`, `area_requirement_checker_04`, `adjacency_access_checker_04`, `tree_constraint_checker_04` | 5 |
| Manipulation | `scale_shape_tool_04`, `stretch_arm_tool_04`, `width_modifier_tool_04`, `courtyard_modifier_tool_04`, `rotate_mirror_tool_04`, `bend_angle_tool_04`, `terrace_step_tool_04` | 7 |
| Evaluation | `spatial_intention_evaluator_04`, `performance_evaluator_04`, `shape_integrity_evaluator_04` | 3 |
| Output | `bake_geometry_id_04` | 1 |
| **Total** | | **19** |

Each tool still needs: GH cluster wiring, real output JSON, and mock stub updated to match real schema.

### Test Cases

3 of 5 planned test cases still to write:
- `test_03_sloped_site.md`
- `test_04_gfa_deficit.md`
- `test_05_irregular_boundary.md`

---

## Next Steps

### Priority 1 — Grasshopper tool implementation (19 tools remaining)
Build GH components for all remaining tools. Each tool needs:
1. GH cluster wiring (input/output wires, Python JSON parser/formatter)
2. MCP registration verified in `team_04_working.gh`
3. Mock stub in the notebook updated to match real output schema
4. Checkbox ticked in `TOOLS_CHECKLIST.md`

Use `gh/tool_definitions/README.md` as the template. Follow the `01_site_boundary_reader.md` spec as a reference pattern.

### Priority 2 — Complete remaining tool specs
Write `gh/tool_definitions/` specs for the remaining 21 tools (prioritise constraint checkers and manipulation tools first).

### Priority 3 — Write remaining 3 test cases
`test_03_sloped_site.md`, `test_04_gfa_deficit.md`, `test_05_irregular_boundary.md`.

### Priority 4 — Test case validation with live GH
Run all 5 test cases against the live MCP server once GH tools are complete.

### Priority 5 — Tune system prompt for live tools
Mock stubs always return `success: true`; real GH tools may return errors or different field names. Adjust `reason.py` prompt guidance and `tools.py` parsing accordingly.

---

## Known Issues

| Issue | Severity | Status |
|---|---|---|
| 19 GH tools not yet implemented | High | In progress — see Priority 1 above |
| GH tool specs written for only 2 of 23 tools | Medium | In progress — write specs before implementing |
| 3 of 5 test cases not yet written | Low | Planned |
| `grandalf` not installed — `print_ascii` silently skipped | Low | Resolved via `try/except` — no action needed |
| Cloudflare rate limits under heavy testing | Medium | Monitor — stagger test runs if hitting 429 errors |
