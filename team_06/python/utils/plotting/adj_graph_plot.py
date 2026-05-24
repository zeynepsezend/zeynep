"""Visualize adjacency graphs (shared walls between rooms)."""

import json
import networkx as nx
import matplotlib.pyplot as plt
from pathlib import Path
from team_06.python.utils.parser.schema_to_adj_graph import create_adjacency_graph_from_layout

# Load the layout file
with open('team_06/layout_inputs/sample_layouts.json', 'r') as f:
    layouts = json.load(f)

# Process each layout
for layout_idx, layout in enumerate(layouts):
    # Create the adjacency graph
    G = create_adjacency_graph_from_layout(layout)

    # Print info
    print(f"\nLayout {layout_idx}:")
    print(f"  Rooms: {G.number_of_nodes()}")
    print(f"  Shared walls: {G.number_of_edges()}")

    # Create the plot
    plt.figure(figsize=(10, 8))
    pos = nx.spring_layout(G, seed=42, k=2)

    # Draw the graph
    nx.draw_networkx_nodes(G, pos, node_color='lightblue', node_size=1500)
    nx.draw_networkx_labels(G, pos, font_size=8)
    nx.draw_networkx_edges(G, pos, width=2, alpha=0.6)

    plt.title(f"Room Adjacency Graph - Layout {layout_idx}\n(Edges = Shared Walls)")
    plt.axis('off')
    plt.tight_layout()

    # Save the plot
    output_dir = Path('team_06/layout_inputs/graph_plots')
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"adjacency_layout_{layout_idx}.png"
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"Saved: {filename}")
    plt.close()

print(f"\nDone! All plots saved to: team_06/layout_inputs/graph_plots/")
