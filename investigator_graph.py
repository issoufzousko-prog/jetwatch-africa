"""
JetWatch Africa — Couche 4 : Graphe Relationnel & Algorithme de Dijkstra

Graphe pondéré orienté pour modéliser les liens entre un dirigeant,
son entourage (famille, politique, proxy) et les actifs étrangers suspects.

Pondération : 1=documenté, 2=recoupement, 3=supposé. Seuil filtre : poids ≤ 6.
"""

import heapq
import json
from dataclasses import dataclass, field, asdict


@dataclass
class Node:
    """Un nœud du graphe : personne ou actif."""
    id: str
    name: str
    category: str   # "racine","famille","entourage","proxy","actif_etranger","societe_ecran","finance"
    degree: int     # 0=dirigeant, 1=famille, 2=entourage, 3=proxy, 4=actif
    details: dict = field(default_factory=dict)


@dataclass
class Edge:
    """Un lien pondéré entre deux nœuds."""
    source: str
    target: str
    relation: str
    weight: int
    source_evidence: str
    evidence_type: str = "inconnu"


class InvestigationGraph:
    """Graphe pondéré orienté pour l'investigation patrimoniale."""

    MAX_PATH_WEIGHT = 6

    def __init__(self):
        self.nodes = {}
        self.adjacency = {}

    def add_node(self, node):
        self.nodes[node.id] = node
        if node.id not in self.adjacency:
            self.adjacency[node.id] = []

    def add_edge(self, edge):
        if edge.source not in self.adjacency:
            self.adjacency[edge.source] = []
        self.adjacency[edge.source].append((
            edge.target, edge.weight, edge.relation,
            edge.source_evidence, edge.evidence_type
        ))

    def dijkstra(self, source_id):
        """Trouve le chemin le plus court (mieux documenté) vers les actifs."""
        if source_id not in self.nodes:
            return {}

        distances = {nid: float('inf') for nid in self.nodes}
        distances[source_id] = 0
        predecessors = {nid: None for nid in self.nodes}
        path_relations = {nid: [] for nid in self.nodes}
        path_sources = {nid: [] for nid in self.nodes}
        path_ev_types = {nid: [] for nid in self.nodes}

        heap = [(0, source_id)]
        visited = set()

        while heap:
            current_dist, current_node = heapq.heappop(heap)
            if current_node in visited:
                continue
            visited.add(current_node)

            for nb_id, weight, relation, src_ev, ev_type in self.adjacency.get(current_node, []):
                if nb_id not in self.nodes:
                    continue
                new_dist = current_dist + weight
                if new_dist < distances[nb_id]:
                    distances[nb_id] = new_dist
                    predecessors[nb_id] = current_node
                    path_relations[nb_id] = path_relations[current_node] + [relation]
                    path_sources[nb_id] = path_sources[current_node] + [src_ev]
                    path_ev_types[nb_id] = path_ev_types[current_node] + [ev_type]
                    heapq.heappush(heap, (new_dist, nb_id))

        asset_cats = {"actif_etranger", "societe_ecran", "finance"}
        results = {}
        for nid, node in self.nodes.items():
            if node.category not in asset_cats:
                continue
            if distances[nid] > self.MAX_PATH_WEIGHT or distances[nid] == float('inf'):
                continue
            path_ids = self._reconstruct_path(predecessors, nid)
            total_w = distances[nid]
            strength = "fort" if total_w <= 2 else ("moyen" if total_w <= 4 else "faible")
            results[nid] = {
                "total_weight": total_w,
                "path_ids": path_ids,
                "path_names": [self.nodes[n].name for n in path_ids],
                "relations": path_relations[nid],
                "sources": path_sources[nid],
                "evidence_types": path_ev_types[nid],
                "asset_name": node.name,
                "asset_category": node.category,
                "asset_details": node.details,
                "strength": strength
            }
        return results

    def _reconstruct_path(self, predecessors, target):
        path = []
        current = target
        while current is not None:
            path.append(current)
            current = predecessors[current]
        return list(reversed(path))

    def format_path_chain(self, path_result):
        """Formate un chemin en chaîne lisible pour le rapport."""
        names = path_result["path_names"]
        relations = path_result["relations"]
        sources = path_result["sources"]
        chain_parts = [f"[{names[0]}]"]
        for i, rel in enumerate(relations):
            chain_parts.append(f" -({rel})-> [{names[i + 1]}]")
        chain = "".join(chain_parts)
        weight_line = f"Poids : {path_result['total_weight']}/{self.MAX_PATH_WEIGHT} — Force : {path_result['strength']}"
        sources_line = f"Sources : {', '.join(s for s in sources if s)}" if any(sources) else "Sources : aucune"
        return f"{chain}\n  {weight_line}\n  {sources_line}"

    def get_stats(self):
        categories = {}
        for node in self.nodes.values():
            categories[node.category] = categories.get(node.category, 0) + 1
        total_edges = sum(len(nb) for nb in self.adjacency.values())
        doc = sum(1 for nb in self.adjacency.values() for _, w, _, _, _ in nb if w == 1)
        ded = sum(1 for nb in self.adjacency.values() for _, w, _, _, _ in nb if w == 2)
        sup = sum(1 for nb in self.adjacency.values() for _, w, _, _, _ in nb if w == 3)
        return {
            "total_nodes": len(self.nodes), "total_edges": total_edges,
            "nodes_by_category": categories,
            "edges_documented": doc, "edges_deduced": ded, "edges_assumed": sup,
            "documentation_ratio": round(doc / total_edges, 2) if total_edges else 0
        }

    def to_json(self):
        return json.dumps({
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": [
                {"source": src, "target": tgt, "relation": rel, "weight": w,
                 "source_evidence": se, "evidence_type": et}
                for src, nbs in self.adjacency.items()
                for tgt, w, rel, se, et in nbs
            ],
            "stats": self.get_stats()
        }, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        graph = cls()
        for nd in data.get("nodes", []):
            graph.add_node(Node(id=nd["id"], name=nd["name"],
                category=nd["category"], degree=nd.get("degree", 4),
                details=nd.get("details", {})))
        for ed in data.get("edges", []):
            graph.add_edge(Edge(source=ed["source"], target=ed["target"],
                relation=ed["relation"], weight=ed.get("weight", 3),
                source_evidence=ed.get("source_evidence", ""),
                evidence_type=ed.get("evidence_type", "inconnu")))
        return graph


def build_graph_from_llm_output(llm_json):
    """Construit le graphe depuis la sortie structurée du LLM."""
    graph = InvestigationGraph()
    for nd in llm_json.get("nodes", []):
        graph.add_node(Node(id=nd["id"], name=nd["name"],
            category=nd.get("category", "inconnu"), degree=nd.get("degree", 4),
            details=nd.get("details", {})))
    for ed in llm_json.get("edges", []):
        graph.add_edge(Edge(source=ed["source"], target=ed["target"],
            relation=ed.get("relation", "lié_à"), weight=ed.get("weight", 3),
            source_evidence=ed.get("source_evidence", "non spécifié"),
            evidence_type=ed.get("evidence_type", "inconnu")))
    return graph


def run_investigation_graph(dirigeant_id, llm_graph_json):
    """Point d'entrée Couche 4 : construit graphe, exécute Dijkstra, retourne résultats."""
    graph = build_graph_from_llm_output(llm_graph_json)
    paths = graph.dijkstra(dirigeant_id)
    formatted_chains = [graph.format_path_chain(pr) for pr in paths.values()]
    stats = graph.get_stats()
    nb = len(paths)
    avg_w = sum(p["total_weight"] for p in paths.values()) / nb if nb else 0
    strong = sum(1 for p in paths.values() if p["strength"] == "fort")
    risk_indicators = {
        "nb_actifs_trouves": nb,
        "poids_moyen_chemins": round(avg_w, 1),
        "liens_forts": strong,
        "degre_dissimulation": "élevé" if avg_w >= 4 else ("moyen" if avg_w >= 2.5 else "faible"),
        "score_transparence": max(0, round(10 - avg_w * 1.5 - nb * 0.5, 1)),
        "score_risque": min(10, round(avg_w * 1.2 + nb * 0.8, 1))
    }
    return {
        "graph_json": graph.to_json(),
        "paths": paths,
        "formatted_chains": formatted_chains,
        "stats": stats,
        "risk_indicators": risk_indicators
    }
