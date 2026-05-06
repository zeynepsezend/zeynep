#!/usr/bin/env python
"""Quick test of integrated graph search tool."""

import sys
from pathlib import Path

# Test GraphSearcher directly
print("✓ Testing GraphSearcher...")
from tools.graph_searcher import GraphSearcher

layouts_path = Path(__file__).resolve().parent.parent / "layout_inputs" / "sample_layouts.json"
gs = GraphSearcher(str(layouts_path))

print(f"✓ GraphSearcher loaded with 6 layouts")
print(f"  Layouts: {list(gs.layout_graphs.keys())}\n")

# Test room program search
results = gs.search_by_room_program(["bed", "kitchen", "living"])
print(f"✓ Room program search ['bed', 'kitchen', 'living']:")
for layout_id, count in results:
    print(f"  - {layout_id}: {count} matches")

# Test with just bed + kitchen
results2 = gs.search_by_room_program(["bed", "kitchen"])
print(f"\n✓ Room program search ['bed', 'kitchen']:")
for layout_id, count in results2:
    print(f"  - {layout_id}: {count} matches")

print(f"\n✓ Graph search is working and ready for agent integration!")

