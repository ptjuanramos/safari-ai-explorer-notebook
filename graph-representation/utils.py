import networkx as nx
import matplotlib.pyplot as plt

RISK_COLORS = {"high": "red", "low": "steelblue"}

def draw_graph(graph, pos: dict, edge_labels: dict, description: str) -> None:
    plt.figure(figsize=(14, 8))

    nx.draw_networkx_nodes(graph, pos, node_color='lightblue', node_size=2500)
    nx.draw_networkx_labels(graph, pos, font_size=8, font_weight='bold')

    edge_colors = [RISK_COLORS.get(d["road"].risk, "gray") for _, _, d in graph.edges(data=True)]
    nx.draw_networkx_edges(graph, pos, edge_color=edge_colors)
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, font_size=7)

    plt.title(description)
    plt.tight_layout()
    plt.show()