import json
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import os
import math
import csv
from collections import defaultdict
import numpy as np

def hex_to_rgb(hex_color):
    """Convert hex color string to RGB tuple (0-1 range for matplotlib)"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16)/255.0 for i in (0, 2, 4))

def get_element_center(geometry):
    """Calculate center point of geometry"""
    if not geometry or len(geometry) == 0:
        return None
    xs = [pt[0] for pt in geometry]
    ys = [pt[1] for pt in geometry]
    return (sum(xs) / len(xs), sum(ys) / len(ys))

def calculate_distance(pt1, pt2):
    """Calculate Euclidean distance between two points"""
    if pt1 is None or pt2 is None:
        return float('inf')
    return math.sqrt((pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2)

def calculate_bounding_box(geometry):
    """Calculate bounding box dimensions"""
    if not geometry or len(geometry) == 0:
        return None, None
    xs = [pt[0] for pt in geometry]
    ys = [pt[1] for pt in geometry]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    return width, height

def load_and_analyze_layout(json_path):
    """Load JSON, create graph with comprehensive relationship analysis"""
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    G = nx.Graph()  # Use undirected for distance-based relationships
    
    base_colors = {
        'room': '#FF6B6B',
        'rooms': '#FF6B6B',
        'door': '#4ECDC4',
        'doors': '#4ECDC4',
        'window': '#45B7D1',
        'windows': '#45B7D1',
        'furniture': '#FFA07A',
        'mep': '#DDA0DD',
        'wall': '#A9A9A9',
        'walls': '#A9A9A9',
        'structure': '#A9A9A9',
        'exterior': '#FFD700',
        'outline': '#FFD700'
    }
    
    all_elements = {}
    relationships = []
    
    # Step 1: Load all elements
    print("  → Loading elements...")
    for category in data.keys():
        if not isinstance(data[category], list):
            continue
        
        color = base_colors.get(category, '#808080')
        
        for element in data[category]:
            if not isinstance(element, dict):
                continue
            
            elem_id = element.get('id')
            if not elem_id:
                continue
            
            elem_name = element.get('name', elem_id)
            geometry = element.get('geometry', [])
            center = get_element_center(geometry)
            width, height = calculate_bounding_box(geometry)
            
            G.add_node(elem_id, 
                      label=elem_name, 
                      type=category,
                      color=color,
                      geometry=geometry,
                      center=center,
                      width=width or 0,
                      height=height or 0)
            
            all_elements[elem_id] = {
                'id': elem_id,
                'name': elem_name,
                'type': category,
                'geometry': geometry,
                'center': center,
                'width': width or 0,
                'height': height or 0,
                'attributes': element.get('attributes', {})
            }
    
    print("    Found {} elements".format(len(all_elements)))
    
    # Step 2: Discover relationships - ID References
    print("  → Discovering ID reference relationships...")
    ref_count = 0
    for elem_id, elem in all_elements.items():
        attributes = elem['attributes']
        
        for attr_name, attr_value in attributes.items():
            if isinstance(attr_value, str) and attr_value in all_elements:
                weight = 1.0
                G.add_edge(elem_id, attr_value, 
                          relationship='references',
                          attribute=attr_name,
                          weight=weight,
                          distance=0)
                relationships.append({
                    'source': elem_id,
                    'target': attr_value,
                    'type': 'references',
                    'attribute': attr_name,
                    'distance': 0,
                    'normalized_distance': 0
                })
                ref_count += 1
            
            elif isinstance(attr_value, list):
                for item in attr_value:
                    if isinstance(item, str) and item in all_elements:
                        weight = 0.9
                        G.add_edge(elem_id, item, 
                                  relationship='references',
                                  attribute=attr_name,
                                  weight=weight,
                                  distance=0)
                        relationships.append({
                            'source': elem_id,
                            'target': item,
                            'type': 'references',
                            'attribute': attr_name,
                            'distance': 0,
                            'normalized_distance': 0
                        })
                        ref_count += 1
    
    print("    Found {} reference relationships".format(ref_count))
    
    # Step 3: Spatial proximity with distance normalization
    print("  → Calculating spatial proximity relationships...")
    elements_list = list(all_elements.values())
    proximity_threshold = 15.0
    all_distances = []
    spatial_relationships = []
    
    for i, elem1 in enumerate(elements_list):
        if elem1['center'] is None:
            continue
        for elem2 in elements_list[i+1:]:
            if elem2['center'] is None:
                continue
            
            distance = calculate_distance(elem1['center'], elem2['center'])
            if distance > 0:
                all_distances.append(distance)
            
            if distance < proximity_threshold and distance > 0:
                spatial_relationships.append((elem1['id'], elem2['id'], distance))
    
    # Normalize distances
    if all_distances:
        min_dist = min(all_distances)
        max_dist = max(all_distances)
        dist_range = max_dist - min_dist if max_dist > min_dist else 1
    else:
        min_dist = 0
        max_dist = 1
        dist_range = 1
    
    proximity_count = 0
    for elem1_id, elem2_id, distance in spatial_relationships:
        normalized_dist = (distance - min_dist) / dist_range if dist_range > 0 else 0
        strength = 1.0 - normalized_dist
        
        G.add_edge(elem1_id, elem2_id, 
                  relationship='spatial_near',
                  weight=strength,
                  distance=round(distance, 2),
                  normalized_distance=round(normalized_dist, 3))
        
        relationships.append({
            'source': elem1_id,
            'target': elem2_id,
            'type': 'spatial_near',
            'attribute': 'proximity',
            'distance': round(distance, 2),
            'normalized_distance': round(normalized_dist, 3)
        })
        proximity_count += 1
    
    print("    Found {} spatial proximity relationships".format(proximity_count))
    print("    Distance range: {:.2f} - {:.2f} units".format(min_dist, max_dist))
    
    # Step 4: Containment relationships (spatial containment in rooms)
    print("  → Discovering containment relationships...")
    contain_count = 0
    for elem_id, elem in all_elements.items():
        room_id = elem['attributes'].get('roomId')
        if room_id and room_id in all_elements:
            G.add_edge(elem_id, room_id, 
                      relationship='contained_in',
                      weight=1.0,
                      distance=0,
                      normalized_distance=0)
            relationships.append({
                'source': elem_id,
                'target': room_id,
                'type': 'contained_in',
                'attribute': 'roomId',
                'distance': 0,
                'normalized_distance': 0
            })
            contain_count += 1
    
    print("    Found {} containment relationships".format(contain_count))
    
    # Step 5: System-based relationships
    print("  → Discovering system group relationships...")
    system_count = 0
    for elem_id, elem in all_elements.items():
        system = elem['attributes'].get('system')
        if system:
            for other_id, other in all_elements.items():
                if other_id != elem_id:
                    if other['attributes'].get('system') == system:
                        G.add_edge(elem_id, other_id, 
                                  relationship='system_group',
                                  weight=0.8,
                                  distance=0,
                                  normalized_distance=0)
                        relationships.append({
                            'source': elem_id,
                            'target': other_id,
                            'type': 'system_group',
                            'attribute': system,
                            'distance': 0,
                            'normalized_distance': 0
                        })
                        system_count += 1
    
    print("    Found {} system group relationships".format(system_count))
    
    # Step 6: Functional relationships (doors connecting rooms)
    print("  → Discovering functional relationships...")
    func_count = 0
    for elem_id, elem in all_elements.items():
        if elem['type'] == 'door':
            connects = elem['attributes'].get('connectsRooms', [])
            if len(connects) >= 2:
                G.add_edge(connects[0], connects[1], 
                          relationship='door_connection',
                          weight=1.0,
                          distance=0,
                          normalized_distance=0)
                relationships.append({
                    'source': connects[0],
                    'target': connects[1],
                    'type': 'door_connection',
                    'attribute': elem_id,
                    'distance': 0,
                    'normalized_distance': 0
                })
                func_count += 1
    
    print("    Found {} functional relationships".format(func_count))
    
    return G, all_elements, base_colors, relationships

def calculate_space_syntax_metrics(G, all_elements):
    """Calculate space syntax and network metrics"""
    
    print("  → Calculating space syntax metrics...")
    
    metrics = {}
    
    # Degree centrality (local importance)
    degree_centrality = nx.degree_centrality(G)
    
    # Betweenness centrality (how much a node connects different parts)
    betweenness_centrality = nx.betweenness_centrality(G)
    
    # Closeness centrality (average distance to other nodes)
    closeness_centrality = nx.closeness_centrality(G)
    
    # Eigenvector centrality (influence in the network)
    try:
        eigenvector_centrality = nx.eigenvector_centrality(G, max_iter=100)
    except:
        eigenvector_centrality = {node: 0 for node in G.nodes()}
    
    # Calculate for each node
    for node in G.nodes():
        metrics[node] = {
            'degree': G.degree(node),
            'degree_centrality': round(degree_centrality.get(node, 0), 3),
            'betweenness_centrality': round(betweenness_centrality.get(node, 0), 3),
            'closeness_centrality': round(closeness_centrality.get(node, 0), 3),
            'eigenvector_centrality': round(eigenvector_centrality.get(node, 0), 3)
        }
    
    print("    Metrics calculated for {} nodes".format(len(metrics)))
    
    return metrics

def visualize_comprehensive_graph(json_path, G, all_elements, base_colors, layout_name, output_file=None):
    """Create comprehensive visualization with space syntax coloring"""
    
    print("  → Generating visualization...")
    
    # Calculate metrics for coloring
    degree_centrality = nx.degree_centrality(G)
    
    # Layout
    pos = nx.spring_layout(G, k=2, iterations=100, seed=42)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(26, 20))
    
    # Draw edges with styling by relationship type
    for (u, v, d) in G.edges(data=True):
        rel_type = d.get('relationship', 'unknown')
        x = [pos[u][0], pos[v][0]]
        y = [pos[u][1], pos[v][1]]
        
        if rel_type == 'references':
            ax.plot(x, y, color='#4169E1', linewidth=1.5, alpha=0.5)
        elif rel_type == 'spatial_near':
            ax.plot(x, y, color='#32CD32', linestyle=':', linewidth=1, alpha=0.3)
        elif rel_type == 'contained_in':
            ax.plot(x, y, color='#FF6B6B', linewidth=2, alpha=0.6, linestyle='-.')
        elif rel_type == 'system_group':
            ax.plot(x, y, color='#9932CC', linestyle='--', linewidth=1.5, alpha=0.5)
        elif rel_type == 'door_connection':
            ax.plot(x, y, color='#FF4500', linewidth=3, alpha=0.8)
        else:
            ax.plot(x, y, color='gray', linewidth=0.5, alpha=0.2)
    
    # Node sizes by degree
    max_degree = max(dict(G.degree()).values()) if G.nodes() else 1
    
    # Draw nodes with matplotlib for proper color support
    for node in G.nodes():
        degree = G.degree(node)
        size = 1000 + (degree / max_degree * 5000) if max_degree > 0 else 1000
        hex_color = G.nodes[node]['color']
        rgb_color = hex_to_rgb(hex_color)  # Convert hex to RGB for matplotlib
        
        nx.draw_networkx_nodes(G, pos,
                              nodelist=[node],
                              node_color=[rgb_color],
                              node_size=[size],
                              ax=ax,
                              alpha=0.85,
                              edgecolors='black',
                              linewidths=2)
    
    # Labels for important nodes
    labels = {}
    for node in G.nodes():
        node_type = G.nodes[node]['type']
        degree = G.degree(node)
        if node_type in ['room', 'door'] or degree >= 3:
            labels[node] = G.nodes[node]['label']
    
    nx.draw_networkx_labels(G, pos, labels, font_size=9, font_weight='bold', ax=ax)
    
    # Comprehensive legend
    legend_elements = [
        Patch(facecolor='#FF6B6B', edgecolor='black', label='Room'),
        Patch(facecolor='#4ECDC4', edgecolor='black', label='Door'),
        Patch(facecolor='#45B7D1', edgecolor='black', label='Window'),
        Patch(facecolor='#FFA07A', edgecolor='black', label='Furniture'),
        Patch(facecolor='#DDA0DD', edgecolor='black', label='MEP System'),
        Patch(facecolor='#A9A9A9', edgecolor='black', label='Wall'),
        plt.Line2D([0], [0], color='#4169E1', linewidth=2, label='Reference'),
        plt.Line2D([0], [0], color='#32CD32', linestyle=':', linewidth=2, label='Spatial Proximity'),
        plt.Line2D([0], [0], color='#FF6B6B', linestyle='-.', linewidth=2, label='Contained In'),
        plt.Line2D([0], [0], color='#9932CC', linestyle='--', linewidth=2, label='System Group'),
        plt.Line2D([0], [0], color='#FF4500', linewidth=3, label='Door Connection')
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=10, title='Legend', title_fontsize=11, framealpha=0.95)
    
    # Statistics box
    stats_text = "Elements: {}\nNodes: {}\nEdges: {}\nDensity: {:.3f}".format(
        len(all_elements),
        G.number_of_nodes(),
        G.number_of_edges(),
        nx.density(G)
    )
    ax.text(0.98, 0.02, stats_text, transform=ax.transAxes, 
           fontsize=10, verticalalignment='bottom', horizontalalignment='right',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    ax.set_title('Comprehensive Building Layout Graph - {}\n(All Elements, Relationships & Space Syntax)'.format(layout_name), 
                fontsize=16, fontweight='bold', pad=20)
    ax.axis('off')
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print("    ✓ Visualization saved: {}".format(output_file))
    
    plt.close()

def export_csv(all_elements, relationships, metrics, layout_name, output_dir="."):
    """Export nodes and edges to CSV files"""
    
    print("  → Exporting to CSV...")
    
    # Export nodes
    nodes_file = os.path.join(output_dir, "{}_nodes.csv".format(layout_name))
    with open(nodes_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Node_ID', 'Name', 'Type', 'Center_X', 'Center_Y', 
                        'Width', 'Height', 'Degree', 'Degree_Centrality', 
                        'Betweenness_Centrality', 'Closeness_Centrality', 
                        'Eigenvector_Centrality', 'Attributes'])
        
        for elem_id, elem in all_elements.items():
            metric = metrics.get(elem_id, {})
            center_x = elem['center'][0] if elem['center'] else ''
            center_y = elem['center'][1] if elem['center'] else ''
            attributes = str(elem['attributes'])
            
            writer.writerow([
                elem_id,
                elem['name'],
                elem['type'],
                center_x,
                center_y,
                elem['width'],
                elem['height'],
                metric.get('degree', 0),
                metric.get('degree_centrality', 0),
                metric.get('betweenness_centrality', 0),
                metric.get('closeness_centrality', 0),
                metric.get('eigenvector_centrality', 0),
                attributes
            ])
    
    print("    ✓ Nodes exported: {} ({} records)".format(nodes_file, len(all_elements)))
    
    # Export edges
    edges_file = os.path.join(output_dir, "{}_edges.csv".format(layout_name))
    with open(edges_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Source', 'Target', 'Relationship_Type', 'Attribute', 
                        'Distance', 'Normalized_Distance', 'Weight'])
        
        for rel in relationships:
            writer.writerow([
                rel['source'],
                rel['target'],
                rel['type'],
                rel['attribute'],
                rel['distance'],
                rel['normalized_distance'],
                rel.get('weight', '')
            ])
    
    print("    ✓ Edges exported: {} ({} records)".format(edges_file, len(relationships)))
    
    # Export metrics summary
    metrics_file = os.path.join(output_dir, "{}_metrics_summary.csv".format(layout_name))
    with open(metrics_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total_Elements', len(all_elements)])
        writer.writerow(['Total_Nodes', len(metrics)])
        writer.writerow(['Total_Relationships', len(relationships)])
        
        # Count by type
        type_counts = defaultdict(int)
        for elem_id, elem in all_elements.items():
            type_counts[elem['type']] += 1
        
        for elem_type, count in sorted(type_counts.items()):
            writer.writerow(['Elements_' + elem_type, count])
        
        # Relationship counts
        rel_counts = defaultdict(int)
        for rel in relationships:
            rel_counts[rel['type']] += 1
        
        for rel_type, count in sorted(rel_counts.items()):
            writer.writerow(['Relationships_' + rel_type, count])
    
    print("    ✓ Metrics summary exported: {}".format(metrics_file))

# Main execution
if __name__ == "__main__":
    json_path = r"c:\Users\User\Desktop\00-MaCAD\GitHub\AIAStudio_test\Layouts\industrial_01.json"
    output_dir = r"c:\Users\User\Desktop\00-MaCAD\GitHub\AIAStudio_test"
    layout_name = os.path.splitext(os.path.basename(json_path))[0]
    
    print("\n" + "="*70)
    print("COMPREHENSIVE BUILDING LAYOUT GRAPH GENERATOR")
    print("="*70)
    print("\nPhase 1: Loading and Analyzing Layout...")
    
    try:
        G, all_elements, base_colors, relationships = load_and_analyze_layout(json_path)
        
        print("\nPhase 2: Calculating Space Syntax Metrics...")
        metrics = calculate_space_syntax_metrics(G, all_elements)
        
        print("\nPhase 3: Generating Visualizations...")
        visualize_comprehensive_graph(json_path, G, all_elements, base_colors, layout_name,
                                     output_file=os.path.join(output_dir, "{}_comprehensive.png".format(layout_name)))
        
        print("\nPhase 4: Exporting Data...")
        export_csv(all_elements, relationships, metrics, layout_name, output_dir)
        
        print("\n" + "="*70)
        print("✓ ANALYSIS COMPLETE!")
        print("="*70)
        print("\nGenerated Files:")
        print("  • {}_comprehensive.png - Network visualization".format(layout_name))
        print("  • {}_nodes.csv - Node data with metrics".format(layout_name))
        print("  • {}_edges.csv - Edge data with relationships".format(layout_name))
        print("  • {}_metrics_summary.csv - Summary statistics".format(layout_name))
        print("\nSummary Statistics:")
        print("  Elements: {}".format(len(all_elements)))
        print("  Relationships Discovered: {}".format(len(relationships)))
        print("  Network Density: {:.3f}".format(nx.density(G)))
        print("="*70 + "\n")
        
    except Exception as e:
        print("\n✗ ERROR: {}".format(str(e)))
        import traceback
        traceback.print_exc()
