# Test Workflow Without LLM

This test script allows you to simulate the complete agent workflow without needing an actual LLM. It combines graph search, filtering, and MCP tool calls.

## Usage

### Run a custom prompt
```bash
python test_workflow.py "look for the layout with 2 bedroom and 2 bathrooms and delete the kitchen"
```

### Run predefined tests
```bash
# Just search (no modification)
python test_workflow.py --test search

# Full workflow: search, filter, delete
python test_workflow.py --test filter_delete

# Run all tests
python test_workflow.py --test all
```

## How It Works

### 1. Mock LLM Parser
Parses natural language prompts into structured tool calls:
- `"find layouts with X bedroom Y bathroom"` → `layout_graph_search`
- `"delete room"` → `layout_filter` + `delete_room_06`

### 2. State Management
`WorkflowState` persists data across steps:
```
Graph Search → candidate_layouts
    ↓
Filter → current_layout_json (in state)
    ↓
MCP Tools → Use layout from state (no parameter passing)
```

### 3. Tool Execution
Tools are called sequentially with the state:
- **layout_graph_search**: Search for layouts by room topology
- **layout_filter**: Load full layout data into state
- **delete_room_06**: Call MCP tool using state layout

## Example Output

```
======================================================================
🚀 EXECUTING WORKFLOW: 'find layouts with 1 bedroom and 1 bathroom'
======================================================================

🤖 [MOCK LLM] Parsing prompt: 'find layouts with 1 bedroom and 1 bathroom'
  → Step 1: Search for programs ['bed', 'bath']

📍 Step 1/1: layout_graph_search
   Arguments: {'programs': ['bed', 'bath'], 'connection_type': 'any'}

🔍 [GRAPH SEARCH] Searching for: ['bed', 'bath'] (connection: any)
  Found 6 matching layouts:
    1. layout-1 (score: 0.500)
    2. layout-2 (score: 0.400)
    ...

======================================================================
✅ WORKFLOW COMPLETE
======================================================================

📊 Final State:
  • Selected Layout: None
  • Available Candidates: 6
  • Last Action: Graph search found 6 layouts
  • Current Rooms: 0 rooms in layout
```

## Files

- `test_workflow.py` - Main test script with MockLLM and orchestrator
- `test_workflow_no_llm.ipynb` - Jupyter notebook version (for interactive exploration)

## Notes

Use **`test_workflow.py`** for:
- CI/CD pipelines
- Scripted testing
- Version control
- Running from command line

Use **`test_workflow_no_llm.ipynb`** for:
- Interactive exploration
- Debugging step-by-step
- Visual output and inspection
