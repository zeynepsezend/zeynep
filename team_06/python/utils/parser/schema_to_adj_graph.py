"""Create an adjacency graph based on shared walls between rooms."""

import json
import networkx as nx
from pathlib import Path


def extract_wall_segments(geometry):
    """
    Extract individual line segments from a geometry.
    
    A geometry is a list of points like [[5.0, 0.0], [5.0, 5.0], [3.0, 5.0], [3.0, 0.0]]
    This function returns the edges (line segments) between consecutive points.
    
    Args:
        geometry: List of [x, y] coordinates forming a closed polygon or line
        
    Returns:
        List of line segments, each segment is ((x1, y1), (x2, y2))
    """
    segments = []
    
    # Loop through points and create segments between consecutive points
    for i in range(len(geometry) - 1):
        point1 = tuple(geometry[i])
        point2 = tuple(geometry[i + 1])
        # Store segments in sorted order for easier comparison
        segment = tuple(sorted([point1, point2]))
        segments.append(segment)
    
    return segments


def segments_overlap(seg1, seg2, tolerance=0.01):
    """
    Check if two line segments overlap or are the same.
    
    Two segments overlap if they are on the same line and share a portion.
    For simplicity, we check if they are identical or very close.
    
    Args:
        seg1: First segment ((x1, y1), (x2, y2))
        seg2: Second segment ((x1, y1), (x2, y2))
        tolerance: How close coordinates need to be to be considered equal
        
    Returns:
        True if segments overlap, False otherwise
    """
    (p1_start, p1_end) = seg1
    (p2_start, p2_end) = seg2
    
    # Check if segments are on the same line and overlap
    # For now, we do exact matching (within tolerance)
    if (abs(p1_start[0] - p2_start[0]) < tolerance and 
        abs(p1_start[1] - p2_start[1]) < tolerance and
        abs(p1_end[0] - p2_end[0]) < tolerance and 
        abs(p1_end[1] - p2_end[1]) < tolerance):
        return True
    
    return False


def rooms_share_wall(room1, room2, walls):
    """
    Check if two rooms share a wall.
    
    A wall is shared if:
    - There is a wall element in the layout
    - One edge of room1's geometry overlaps with that wall
    - One edge of room2's geometry overlaps with that same wall
    
    Args:
        room1: First room dict (must have 'geometry' key)
        room2: Second room dict (must have 'geometry' key)
        walls: List of wall geometries from layout['structure']
        
    Returns:
        True if rooms share a wall, False otherwise
    """
    # Extract all edges (line segments) from both rooms
    room1_segments = extract_wall_segments(room1['geometry'])
    room2_segments = extract_wall_segments(room2['geometry'])
    
    # Check each wall in the structure
    for wall in walls:
        wall_geometry = wall['geometry']
        
        # A wall is a line segment (2 points) or a line with multiple points
        # Extract all segments from the wall geometry
        wall_segments = extract_wall_segments(wall_geometry)
        
        # Check if room1 has a segment that matches a wall segment
        room1_has_wall = False
        for room_seg in room1_segments:
            for wall_seg in wall_segments:
                if segments_overlap(room_seg, wall_seg):
                    room1_has_wall = True
                    break
            if room1_has_wall:
                break
        
        # Check if room2 has a segment that matches the same wall segment
        room2_has_wall = False
        if room1_has_wall:
            for room_seg in room2_segments:
                for wall_seg in wall_segments:
                    if segments_overlap(room_seg, wall_seg):
                        room2_has_wall = True
                        break
                if room2_has_wall:
                    break
        
        # If both rooms have this wall, they share it!
        if room1_has_wall and room2_has_wall:
            return True
    
    return False


def create_adjacency_graph_from_layout(layout: dict) -> nx.Graph:
    """
    Create a NetworkX graph from a layout JSON object based on shared walls.
    
    Nodes are room IDs with program attributes.
    Edges represent walls shared between rooms.
    
    Args:
        layout: Dictionary with 'rooms' and 'structure' keys
        
    Returns:
        NetworkX graph where edges represent shared walls
    """
    graph = nx.Graph()
    
    # Add a node for each room
    for room in layout['rooms']:
        room_id = room['id']
        attrs = room.get('attributes', {})
        program = attrs.get('program', '') or room.get('program', '')
        name = room.get('name', '')
        graph.add_node(room_id, name=name, program=program)
    
    # Get all walls from the structure
    walls = layout.get('structure', [])
    
    # Check each pair of rooms to see if they share a wall
    rooms = layout['rooms']
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            room1 = rooms[i]
            room2 = rooms[j]
            
            # Check if these two rooms share a wall
            if rooms_share_wall(room1, room2, walls):
                room_id_1 = room1['id']
                room_id_2 = room2['id']
                
                # Add an edge between the two rooms
                graph.add_edge(room_id_1, room_id_2, weight=1)
    
    return graph


def generate_adjacency_graphs_from_directory(layouts_dir: str, output_path: str = None) -> None:
    """
    Generate adjacency graphs from a directory of layout JSON files.
    
    Reads all JSON files from a directory, creates adjacency graphs for each,
    and saves them to a single output JSON file.

    Args:
        layouts_dir: Path to directory containing layout JSON files
        output_path: Path to save graphs JSON (default: adjacency_graphs.json in layouts_dir)
    """
    layouts_dir = Path(layouts_dir)
    layout_files = sorted(layouts_dir.glob("*.json"))

    if not layout_files:
        print(f"No JSON files found in {layouts_dir}")
        return

    graphs_data = {}
    
    # Process each layout file
    for layout_file in layout_files:
        print(f"Processing {layout_file.name}...")
        
        with open(layout_file, 'r') as f:
            layout_data = json.load(f)
        
        # Skip if layout doesn't have required fields
        if 'rooms' not in layout_data or 'structure' not in layout_data:
            print(f"  Skipped: missing 'rooms' or 'structure'")
            continue
        
        layout_id = layout_data.get('layoutId', layout_file.stem)
        graph = create_adjacency_graph_from_layout(layout_data)
        
        # Convert NetworkX graph to JSON format
        graphs_data[layout_id] = nx.node_link_data(graph)
        print(f"  Created graph with {graph.number_of_nodes()} rooms and {graph.number_of_edges()} shared walls")

    # Save all graphs to output file
    if output_path is None:
        output_path = str(layouts_dir / "adjacency_graphs.json")

    with open(output_path, 'w') as f:
        json.dump(graphs_data, f, indent=2)

    print(f"\nDone! Generated {len(graphs_data)} adjacency graphs -> {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate adjacency graphs based on shared walls from layout JSON files."
    )
    parser.add_argument(
        "--dir", 
        help="Directory of layout JSON files to process"
    )
    parser.add_argument(
        "--output", 
        help="Output path for graphs JSON", 
        default=None
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent.parent

    if args.dir:
        layouts_dir = Path(args.dir) if Path(args.dir).is_absolute() else repo_root / "layout_inputs" / args.dir
        print(f"Generating adjacency graphs from directory: {layouts_dir}")
        generate_adjacency_graphs_from_directory(str(layouts_dir), args.output)
    else:
        # Default to team_06 layout inputs
        layouts_dir = repo_root / "team_06" / "layout_inputs"
        if layouts_dir.exists():
            print(f"Generating adjacency graphs from directory: {layouts_dir}")
            generate_adjacency_graphs_from_directory(str(layouts_dir), args.output)
        else:
            print(f"Default directory not found: {layouts_dir}")

