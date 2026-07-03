import networkx as nx
from dataclasses import dataclass

@dataclass
class Road:
    travel_time: int
    road_type: str
    risk: str

NODE_POS = {
    "Karatu":        (0.0,  0.0),
    "Lodoare Gate":  (0.7,  1.2),
    "Olduvai Gorge": (1.5,  0.8),
    "Naabi Hill":    (2.5,  1.0),
    "Simba Kopjes":  (3.0,  1.8),
    "Ndutu":         (2.8,  0.3),
    "Seronera":      (4.0,  1.5),
    "Moru Kopjes":   (4.5,  0.1),
    "Retima":        (5.0,  1.8),
    "Lobo":          (6.0,  2.0),
    "Klein's Gate":  (7.0,  1.5),
}

WAYPOINTS = [
    "Karatu",
    "Lodoare Gate",
    "Olduvai Gorge",
    "Naabi Hill",
    "Simba Kopjes",
    "Ndutu",
    "Moru Kopjes",
    "Seronera",
    "Retima",
    "Lobo",
    "Klein's Gate"
]

EDGES: list[tuple[str, str, Road]] = [
    ("Karatu",        "Lodoare Gate",  Road(60,  "main_road",    "low")),
    ("Lodoare Gate",  "Olduvai Gorge", Road(45,  "main_road",    "low")),
    ("Olduvai Gorge", "Naabi Hill",    Road(60,  "main_road",    "low")),
    ("Naabi Hill",    "Simba Kopjes",  Road(30,  "direct_track", "high")),
    ("Naabi Hill",    "Ndutu",         Road(75,  "direct_track", "high")),
    ("Simba Kopjes",  "Seronera",      Road(45,  "main_road",    "low")),
    ("Ndutu",         "Seronera",      Road(90,  "main_road",    "low")),
    ("Seronera",      "Moru Kopjes",   Road(45,  "black_cotton", "high")),
    ("Seronera",      "Retima",        Road(60,  "main_road",    "low")),
    ("Retima",        "Lobo",          Road(90,  "black_cotton", "high")),
    ("Lobo",          "Klein's Gate",  Road(60,  "main_road",    "low")),
    ("Moru Kopjes",   "Karatu",        Road(120, "main_road",    "low")),
    ("Klein's Gate",  "Karatu",        Road(180, "main_road",    "low")),
]

def get_default_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(WAYPOINTS)

    for origin, destination, road in EDGES:
        graph.add_edge(origin, destination, road=road)

    return graph