"""
export_mermaid.py -- Export the Comfort Copilot graph as a Mermaid diagram.

The _DIAGRAM constant below IS the diagram -- identical to comfort_copilot_graph_v4.mermaid.
Running this script:
  1. Builds graph.py and checks all expected nodes are present
  2. Saves comfort_copilot_graph_auto.mermaid to the python/ folder

When you change graph.py structure (add/remove nodes):
  - Update the _NODE_MAP below
  - Update the _DIAGRAM constant to reflect the new structure
  - Run this script to verify and publish

Run from the python/ directory:
    python export_mermaid.py
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class _MockContext:
    llm_simple: Any = None
    llm: Any = None
    mcp_client: Any = None
    layout_input_dir: Path = Path(".")
    layout_output_dir: Path = Path(".")


# Maps diagram node IDs to graph.py node names -- used for structural verification
_NODE_MAP = {
    "GREET":              "greet",
    "USER_PROFILER":      "user_profiler",
    "INTENT_CLASSIFIER":  "intent_classifier",
    "CHITCHAT":           "chitchat",
    "INSPIRE":            "inspire",
    "LOAD_LAYOUT":        "load_layout",
    "OVERVIEW_RESPOND":   "overview_respond",
    "PERSONA_BUILDER":    "persona_builder",
    "PERSONA_VALIDATOR":  "persona_validator",
    "ADVISOR":            "advisor",
    "ROUTE_INTENT":       "route_intent",
    "ANALYZE":            "analyze",
    "SCORE_INTERP":       "score_interpreter",
    "DETECT":             "detect",
    "CONFLICT_R":         "conflict_reasoner",
    "SUGGEST":            "suggest",
    "SUGGEST_CRIT":       "suggestion_critic",
    "RESPOND":            "respond",
    "EVALUATOR":          "evaluator",
    "FACT_CHECK":         "fact_checker",
    "WHAT_NEXT":          "what_next",
    "CHANGE_MATERIAL":    "change_material",
    "MODIFY_GLAZING":     "modify_glazing",
    "ADD_FURNITURE":      "add_furniture",
    "COMPARE_VERSIONS":   "compare_versions",
    "TOPOLOGIC":          "topologic_analysis",
    "PERSONA_COMPARISON": "persona_comparison",
    "BIOPHILIC_AUDIT":    "biophilic_audit",
}


def _verify_graph(app):
    """Warn about any node mismatches between diagram and graph.py."""
    actual   = set(app.get_graph().nodes.keys()) - {"__start__", "__end__"}
    expected = set(_NODE_MAP.values())
    missing_in_diagram = actual   - expected
    missing_in_graph   = expected - actual
    ok = True
    if missing_in_diagram:
        print("WARNING -- in graph.py but NOT in diagram: {}".format(missing_in_diagram))
        ok = False
    if missing_in_graph:
        print("WARNING -- in diagram but NOT in graph.py: {}".format(missing_in_graph))
        ok = False
    if ok:
        print("OK -- all {} nodes verified against graph.py".format(len(actual)))


# ── THE DIAGRAM ───────────────────────────────────────────────────────────────
# This is the definitive diagram, matching comfort_copilot_graph_v4.mermaid exactly.
# Edit here when the graph structure changes, then re-run this script to verify.

_DIAGRAM = r"""---
config:
  flowchart:
    curve: basis
---
flowchart TB

    %% ── NODE TYPE STYLES ────────────────────────────────────────────────
    classDef llm        fill:#D6E8F8,stroke:#4A90D9,stroke-width:2px,color:#1a1a1a
    classDef py         fill:#D5EFDC,stroke:#5BAD72,stroke-width:2px,color:#1a1a1a
    classDef mcp        fill:#FDDCBC,stroke:#E07B3A,stroke-width:2px,color:#1a1a1a
    classDef newnode    fill:#EAD5F5,stroke:#9B59B6,stroke-width:2.5px,stroke-dasharray:5 3,color:#1a1a1a
    classDef specialist fill:#FCE4D6,stroke:#A0522D,stroke-width:2px,color:#1a1a1a
    classDef ph         fill:#FFFDE7,stroke:#F9A825,stroke-width:1.5px,stroke-dasharray:4 2,color:#555
    classDef terminal   fill:#2C3E50,stroke:#2C3E50,color:#fff

    %% ── CONVERSATION PROMPT STYLES ── Blue=Architect  Green=Student  Purple=Client
    classDef convA  fill:#DBEAFE,stroke:#2563EB,stroke-width:1.5px,color:#1E3A8A
    classDef convS  fill:#D1FAE5,stroke:#059669,stroke-width:1.5px,color:#064E3B
    classDef convC  fill:#EDE9FE,stroke:#7C3AED,stroke-width:1.5px,color:#4C1D95

    START([START]):::terminal
    END_F([END]):::terminal

    %% ── ① ENTRY ─────────────────────────────────────────────────────────
    subgraph ENTRY["① ENTRY — first turn only · skipped on follow-ups"]
        GREET["GREET  [LLM]\n'Who are you? What brings you here?'"]:::newnode
        PA1>"🔵 A: 'I'm an architect — designing\nfor a single parent, 3 kids, layout 201'"]:::convA
        PS1>"🟢 S: 'Hi. I'm here to learn.\nI'm nobody special'"]:::convS
        PC1>"🟣 C: 'I'm 25F, living with my elderly\ngrandma — let's look at layout 201'"]:::convC
        USER_PROFILER["USER_PROFILER  [LLM]\nclassifies: architect · client · learner\nextracts any layout or persona hints\nwrites → user_type · initial_context"]:::newnode
    end

    %% ── ② ROUTING ────────────────────────────────────────────────────────
    subgraph ROUTING["② ROUTING — replaces keyword preprocess"]
        INTENT_CLASSIFIER["INTENT_CLASSIFIER  [LLM]\nreads meaning, not keywords\nroutes: comfort · overview · inspire\nchitchat · what-if · compare · biophilic · topologic"]:::newnode
    end

    CHITCHAT["CHITCHAT  [LLM]\npeer mode · educational register\nknows what it can and cannot do\n'I can't tell you about you — tell me about you'\ndetects if user shifts to analysis intent"]:::llm
    PS2>"🟢 S: 'What exactly can you do?\nAnd what can't you do?'"]:::convS

    INSPIRE["INSPIRE  [PY]  Phase 3 placeholder"]:::py
    OVERVIEW_RESPOND["OVERVIEW_RESPOND  [LLM]\nlists rooms · no analysis · no persona"]:::llm

    %% ── ③ PERSONA CHAIN ──────────────────────────────────────────────────
    subgraph PERSONA["③ PERSONA CHAIN"]
        LOAD_LAYOUT["LOAD_LAYOUT  [PY]\nskips if same layout already in session"]:::py
        PA2>"🔵 A: 'Single mum, 38, works from home.\nQuiet and thermal comfort matter most'"]:::convA
        PC2>"🟣 C: 'She's 78, hard of hearing,\nvery sensitive to light and temperature'"]:::convC
        PERSONA_BUILDER["PERSONA_BUILDER  [LLM]\nfluid · multi-turn dialogue\nhandles single and dual occupancy\nwrites → persona_profile  (not a category)"]:::newnode
        PERSONA_VALIDATOR["PERSONA_VALIDATOR  [LLM]\nage · sensory priority · use pattern?\nreturns COMPLETE or one specific question\nmax 3 turns"]:::specialist
        PA3>"🔵 A: 'Honestly I have no idea\nwhere to start — can you advise?'"]:::convA
        ADVISOR["ADVISOR  [LLM]\nreviews layout + persona_profile\nrecommends one clear starting path\n'I'd suggest starting with...'"]:::newnode
    end

    %% ── ④ ROUTE INTENT ───────────────────────────────────────────────────
    subgraph INTENT["④ ROUTE INTENT"]
        PA4>"🔵 A: 'Full analysis —\nI want everything'"]:::convA
        PC3>"🟣 C: 'Analyze for both of us —\nhow does it feel for her vs for me?'"]:::convC
        PS3>"🟢 S: 'OK I want to try!\nLayout 201, elderly user'"]:::convS
        ROUTE_INTENT["ROUTE_INTENT  [LLM]\nanalyze · detect · full\nwhat-if · compare · biophilic · topologic"]:::llm
    end

    %% ── ⑤ MAIN ANALYSIS CHAIN ────────────────────────────────────────────
    subgraph ANALYSIS["⑤ MAIN ANALYSIS CHAIN"]
        ANALYZE["ANALYZE  [MCP]\ncompute_comfort_scores\n6 senses · all rooms · per persona_profile"]:::mcp
        SCORE_INTERP["SCORE_INTERPRETER  [LLM]\nwhat do scores MEAN for this persona?\nnot the number — the human experience\nfeeds all downstream paths"]:::specialist
        DETECT["DETECT  [MCP]\ndetect_sensorial_conflicts\nflags senses below persona threshold"]:::mcp
        CONFLICT_R["CONFLICT_REASONER  [LLM]\nWHY did it fail?\norientation · materials · adjacency\nventilation · spatial layout"]:::specialist
        SUGGEST["SUGGEST  [MCP]\ngenerate_suggestions\nactionable fix per failing sense per room"]:::mcp
        SUGGEST_CRIT["SUGGESTION_CRITIC  [LLM]\nfeasible within this layout?\nranked by persona priority?\nunintended consequences on other senses?"]:::specialist
    end

    %% ── ⑤a MODIFICATION TOOLS ────────────────────────────────────────────
    subgraph MOD["⑤a MODIFICATION TOOLS  →  re-score via ANALYZE"]
        PA5>"🔵 A: 'What if I change the bedroom\nwall to acoustic absorbent panels?'"]:::convA
        PC5>"🟣 C: 'Can we change the living room\nglazing for grandma?'"]:::convC
        CHANGE_MATERIAL["CHANGE_MATERIAL  [PH · MCP]  P1\nmodify room material in layout copy\nre-triggers ANALYZE for new scores\ncloses the suggest → implement → rescore loop"]:::ph
        MODIFY_GLAZING["MODIFY_GLAZING  [PH · MCP]  P3\nchange glazingRatio or glazingType\naffects thermal + visual scores"]:::ph
        ADD_FURNITURE["ADD_FURNITURE  [PH · MCP]  P3\nadd furniture element incl. plants\naffects acoustic · spatial · tactile\nalso triggered by BIOPHILIC_AUDIT"]:::ph
        COMPARE_VERSIONS["COMPARE_VERSIONS  [PH · MCP]  P2\nbefore / after score delta\nshows exact impact of the modification\nfeeds into SCORE_INTERP"]:::ph
    end

    %% ── ⑤b SPATIAL TOOL ──────────────────────────────────────────────────
    subgraph SPATIAL["⑤b SPATIAL TOOL  →  feeds CONFLICT_REASONER"]
        TOPOLOGIC["TOPOLOGIC_ANALYSIS  [PH · MCP]  P1\nroom adjacency graph via TopologicPy\ncross-room comfort propagation\nnoisy kitchen next to quiet bedroom?\nwrites → adjacency_graph"]:::ph
    end

    %% ── ⑤c PERSONA COMPARISON ───────────────────────────────────────────
    subgraph PERSONAS_COMP["⑤c PERSONA COMPARISON  →  feeds SCORE_INTERP"]
        PC4>"🟣 C: 'Show me her comfort vs mine\nside by side — who suffers where?'"]:::convC
        PERSONA_COMPARISON["PERSONA_COMPARISON  [PH · LLM+MCP]  P2\nsame layout · two persona_profiles\nruns ANALYZE twice\nshows delta: who suffers where and why"]:::ph
    end

    %% ── ⑤d BIOPHILIC TOOL ────────────────────────────────────────────────
    subgraph BIO["⑤d BIOPHILIC TOOL  →  'Talk Green To Me'"]
        PS4>"🟢 S: 'Interesting! Now what about\nthe biophilic analysis?'"]:::convS
        BIOPHILIC_AUDIT["BIOPHILIC_AUDIT  [PH · LLM+MCP]  P3\n'Talk Green To Me'\nplants · natural materials · views\nglazing · natural ventilation\nscores biophilic richness per room"]:::ph
    end

    %% ── ⑥ QUALITY LOOP ───────────────────────────────────────────────────
    subgraph QUALITY["⑥ QUALITY LOOP — specialists talk until it's right"]
        RESPOND["RESPOND  [LLM]\nuser-type + depth aware\nprofessional · peer · accessible\nformat driven by: analyze · detect · full"]:::llm
        EVALUATOR["EVALUATOR  [LLM]\ncoherent? complete? right tone for user type?\nreturns APPROVED or REVISE + specific instructions"]:::specialist
        FACT_CHECK["FACT_CHECKER  [LLM]\nevery score traceable to tool output?\nno invented rooms or senses?\nreturns VERIFIED or exact DISCREPANCY"]:::specialist
    end

    %% ── ⑦ FEEDBACK LOOP ──────────────────────────────────────────────────
    subgraph FEEDBACK["⑦ FEEDBACK LOOP — the conversation continues"]
        PA6>"🔵 A: 'What should I fix first\nfor the parent's bedroom?'"]:::convA
        PS5>"🟢 S: 'Wow. Can I try the\nbiophilic analysis now?'"]:::convS
        PC6>"🟣 C: 'Now compare both personas\non the new modified layout'"]:::convC
        WHAT_NEXT["WHAT_NEXT  [LLM]\nTHE FEEDBACK LOOP\ndeeper · what-if · compare\nbiophilic · continue chatting · done"]:::newnode
    end

    OUTPUT_WRITER["OUTPUT_WRITER  [PY]  post-graph\nwrites resulting_layout/ JSON · non-fatal"]:::py

    %% ── EDGES ────────────────────────────────────────────────────────────
    START --> GREET
    GREET -.-> PA1 & PS1 & PC1
    PA1 & PS1 & PC1 --> USER_PROFILER

    USER_PROFILER -->|"architect · client"| INTENT_CLASSIFIER
    USER_PROFILER -->|learner| CHITCHAT
    CHITCHAT -.-> PS2
    PS2 --> CHITCHAT

    CHITCHAT -->|"chitchat response"| WHAT_NEXT
    CHITCHAT -->|"analysis intent detected"| INTENT_CLASSIFIER

    INTENT_CLASSIFIER -->|image| INSPIRE --> WHAT_NEXT
    INTENT_CLASSIFIER -->|"overview · comfort · tools"| LOAD_LAYOUT
    LOAD_LAYOUT -.->|overview| OVERVIEW_RESPOND --> WHAT_NEXT
    INTENT_CLASSIFIER -->|chitchat| CHITCHAT

    LOAD_LAYOUT -.->|analysis| PERSONA_BUILDER
    PERSONA_BUILDER -.-> PA2 & PC2
    PA2 & PC2 --> PERSONA_VALIDATOR
    PERSONA_VALIDATOR -.->|"incomplete - end turn"| END_F
    PERSONA_VALIDATOR -->|unsure| PA3 --> ADVISOR --> ROUTE_INTENT
    PERSONA_VALIDATOR -->|ready| ROUTE_INTENT

    ROUTE_INTENT -.-> PA4 & PC3
    WHAT_NEXT -.-> PS3
    PS3 & PA4 & PC3 --> ROUTE_INTENT

    ROUTE_INTENT -->|"analyze · detect · full"| ANALYZE
    ANALYZE -->|"initial analysis"| SCORE_INTERP
    SCORE_INTERP -->|"detect · full"| DETECT
    SCORE_INTERP -->|"analyze only"| RESPOND
    DETECT --> CONFLICT_R
    CONFLICT_R -->|full| SUGGEST --> SUGGEST_CRIT --> RESPOND
    CONFLICT_R -->|detect| RESPOND

    ROUTE_INTENT -->|"what-if: modify"| PA5 & PC5
    PA5 --> CHANGE_MATERIAL
    PC5 --> MODIFY_GLAZING
    CHANGE_MATERIAL & MODIFY_GLAZING & ADD_FURNITURE -->|"re-score"| ANALYZE
    ANALYZE -->|"after modification"| COMPARE_VERSIONS --> SCORE_INTERP

    ROUTE_INTENT -->|topologic| TOPOLOGIC --> CONFLICT_R

    ROUTE_INTENT -->|"compare personas"| PC4 --> PERSONA_COMPARISON --> SCORE_INTERP

    ROUTE_INTENT -->|biophilic| PS4 --> BIOPHILIC_AUDIT
    BIOPHILIC_AUDIT -->|"opt: add plants"| ADD_FURNITURE
    BIOPHILIC_AUDIT -->|"direct"| SCORE_INTERP

    RESPOND --> EVALUATOR
    EVALUATOR -->|"REVISE — max 3"| RESPOND
    EVALUATOR -->|APPROVED| FACT_CHECK
    FACT_CHECK -->|"DISCREPANCY — max 3"| RESPOND
    FACT_CHECK -->|VERIFIED| WHAT_NEXT
    FACT_CHECK -.->|post-graph| OUTPUT_WRITER

    WHAT_NEXT -.-> PA6 & PS5 & PC6
    PA6 -->|"go deeper · what-if"| ROUTE_INTENT
    PS5 -->|biophilic| ROUTE_INTENT
    PC6 -->|"compare · what-if"| ROUTE_INTENT
    WHAT_NEXT -->|done| END_F
"""


def main():
    from graph import build_graph

    ctx = _MockContext()
    app = build_graph(ctx)

    print("Verifying graph.py structure...")
    _verify_graph(app)
    print()

    output_path = Path(__file__).parent / "comfort_copilot_graph_auto.mermaid"
    output_path.write_text(_DIAGRAM.lstrip('\n'), encoding="utf-8")

    print("Exported: {}".format(output_path))
    print("Open in VS Code (Mermaid Preview) or mermaid.live")


if __name__ == "__main__":
    main()
