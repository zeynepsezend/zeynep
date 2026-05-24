# Permanence_OS

# Description
The Permanence_OS is an LLM-based structural design agent and orchestrator for the AIA26 Studio pipeline. It specializes in structural grid generation, element analysis, and material selection, while also routing queries to the other five specialist agents when broader expertise is needed. The Permanence_OS synthesizes responses across agents to deliver a comprehensive answer. Each agent has its own agent.md with details on its specific capabilities.

# Example Prompts
1. "Add a structural grid to my apartment layout and evaluate whether it can support the loads."
   - The Permanence_OS generates a column grid from the layout outline, runs first-principles beam and column checks (bending, shear, deflection, buckling), prompts the architect for material selection and use-type loads (SDL + LL), and returns a full evaluation table with pass/fail results per element.
2. "I want to open up my living room by removing column C_2 — is that structurally feasible?"
   - The Permanence_OS simulates the column removal, traces the beam chain to the nearest remaining support, re-evaluates the extended span, and presents the architect with options: upgrade the beam section, add a midspan column, or switch to a stronger material. If the architect confirms, the column is removed from the JSON and connected beams are merged into a single longer beam.
3. "What are the section sizes for the CD grid line beams, and which beam has the longest span?"
   - The Permanence_OS reads the per-element layout context directly and answers without running any structural calculations or prompting for material or loads.
4. "I want to build a six-apartment building on a narrow plot — what structural system would work and what will it cost?"
   - The Permanence_OS routes to the Site Agent to analyze the plot constraints, then generates a structural grid and evaluates material options (RCC, Steel, Timber) for the given spans, then routes the structural output to the Regulation & Cost Agent for a cost estimate.
5. "Design an open-plan apartment with as few columns as possible and check if the structure holds."
   - The Permanence_OS routes to the Use Agent for an open-plan layout, then generates the minimal structural grid, runs beam and column evaluations, and if any elements fail automatically cycles through section upgrades or proposes a steel frame to achieve the required spans.
6. "Find the minimum sufficient sections for steel."
   - The Permanence_OS auto-detects steel from the prompt, skips the material picker, and asks only for SDL and live load. It then applies XS steel sections across all elements and upgrades each failing element step by step — returning the smallest possible IPE profiles that pass all checks for the given loads. SDL and live load choices are saved to disk and pre-filled on the next run.
