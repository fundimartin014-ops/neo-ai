import json
import os

GRAPH_FILE = "knowledge_graph.json"


def load_graph():
    if not os.path.exists(GRAPH_FILE):
        return {}
    with open(GRAPH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_graph(graph):
    with open(GRAPH_FILE, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)


def add_relation(subject, relation, obj):
    graph = load_graph()

    if subject not in graph:
        graph[subject] = []

    graph[subject].append({
        "relation": relation,
        "object": obj
    })

    save_graph(graph)


def find_relations(entity):
    graph = load_graph()
    return graph.get(entity, [])
