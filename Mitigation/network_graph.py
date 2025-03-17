import networkx as nx
import matplotlib.pyplot as plt

def draw_network_graph(controllers):
    """Visualize the controller-switch connections with dotted lines between controllers and switches."""
    G = nx.Graph()

    # Add controller nodes
    for controller_id in controllers:
        G.add_node(f"C{controller_id}", color='red', size=1000)  # Prefix 'C' for controllers

    # Collect all switches and sort them in ascending order
    all_switches = sorted(set(switch for data in controllers.values() for switch in data["connected_switches"]))

    # Add switch nodes
    for switch_id in all_switches:
        G.add_node(f"S{switch_id}", color='blue', size=500)  # Prefix 'S' for switches

    # Add edges: Connect switches in ascending order (solid line between switches)
    for i in range(len(all_switches) - 1):
        G.add_edge(f"S{all_switches[i]}", f"S{all_switches[i + 1]}", style="solid")  # Solid line between switches

    # Add edges: Connect each switch to its controller
    for controller_id, data in controllers.items():
        for switch_id in sorted(data["connected_switches"]):
            G.add_edge(f"C{controller_id}", f"S{switch_id}", style="dotted")  # Dotted line between controller and switch

    # Extract node colors and sizes
    node_colors = [G.nodes[n]['color'] for n in G.nodes]
    node_sizes = [G.nodes[n]['size'] for n in G.nodes]

    # Position nodes
    pos = nx.spring_layout(G, seed=42, k=0.5)  # Adjust k for spacing

    # Draw the graph
    plt.figure(figsize=(8, 6))
    nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=node_sizes, edge_color="gray", font_weight="bold")

    # Manually apply dotted lines between controllers and switches
    for u, v, data in G.edges(data=True):
        if data.get('style') == 'dotted':  # Apply dotted style for controller-switch edges
            plt.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], linestyle=':', color='gray', linewidth=2)
        else:  # Apply solid style for switch-switch edges
            plt.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], linestyle='-', color='gray', linewidth=2)

    # Show the graph
    plt.title("Network Graph: Ordered Switches & Dotted Controller Connections")
    plt.show()


#