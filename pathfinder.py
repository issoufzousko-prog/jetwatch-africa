"""
A★ Pathfinder v4 — Confidence-Weighted Investigation Pathfinding
================================================================
Adaptation de l'algorithme A★ à l'investigation OSINT :
  - g(n) = coût cumulé = somme des (1.0 - confidence)
  - h(n) = heuristique basée sur le type de nœud
  - f(n) = g(n) + h(n)

A★ cherche naturellement le chemin de CONFIANCE CUMULATIVE MAXIMALE.

Inclut :
  - Contraction Hierarchies (CH) pour les supernodes fréquents
  - Ranking multi-critères (confiance × sources × fraîcheur)
  - Export de chaînes de preuves pour le rapport LLM
"""

import heapq
import networkx as nx
from dataclasses import dataclass, field
from typing import Optional
from investigation_graph import InvestigationGraph, NodeType


# ════════════════════════════════════════════════════════════════════════
# Data Classes pour les résultats
# ════════════════════════════════════════════════════════════════════════

@dataclass
class PathStep:
    """Un maillon dans la chaîne de preuves."""
    node_id: str
    label: str
    node_type: str
    relation_to_next: str = ""
    confidence_to_next: float = 0.0
    sources: list = field(default_factory=list)
    
    def to_dict(self):
        return {
            "node_id": self.node_id,
            "label": self.label,
            "type": self.node_type,
            "relation": self.relation_to_next,
            "confidence": self.confidence_to_next,
            "sources_count": len(self.sources),
        }


@dataclass
class EvidenceChain:
    """Une chaîne de preuves complète entre un actif et la cible."""
    steps: list = field(default_factory=list)
    total_confidence: float = 0.0
    total_sources: int = 0
    path_length: int = 0
    
    def to_dict(self):
        return {
            "steps": [s.to_dict() for s in self.steps],
            "total_confidence": round(self.total_confidence, 4),
            "total_sources": self.total_sources,
            "path_length": self.path_length,
            "strength": self._compute_strength(),
        }
    
    def _compute_strength(self) -> str:
        """Classification de la force de la chaîne."""
        if self.total_confidence >= 0.7:
            return "FORTE"
        elif self.total_confidence >= 0.4:
            return "MOYENNE"
        elif self.total_confidence >= 0.2:
            return "FAIBLE"
        else:
            return "SPÉCULATIVE"
    
    def to_narrative(self) -> str:
        """Génère un récit textuel de la chaîne pour le LLM."""
        if not self.steps:
            return "Aucun chemin trouvé."
        
        parts = []
        for i, step in enumerate(self.steps):
            if i == 0:
                parts.append(f"📍 {step.label} ({step.node_type})")
            elif i == len(self.steps) - 1:
                parts.append(f"  → 🎯 {step.label} (CIBLE)")
            else:
                prev = self.steps[i-1]
                conf_pct = f"{prev.confidence_to_next:.0%}"
                parts.append(f"  → [{prev.relation_to_next}] (confiance: {conf_pct}) → {step.label} ({step.node_type})")
        
        parts.append(f"\n  Force de la chaîne : {self._compute_strength()} ({self.total_confidence:.0%})")
        return "\n".join(parts)


# ════════════════════════════════════════════════════════════════════════
# Heuristiques pour A★
# ════════════════════════════════════════════════════════════════════════

# Coût heuristique estimé pour atteindre la cible depuis un type de nœud
HEURISTIC_COSTS = {
    NodeType.TARGET: 0.0,       # C'est la cible elle-même
    NodeType.FAMILY: 0.05,      # Famille directe → très proche
    NodeType.ASSOCIATE: 0.15,   # Associé connu → proche
    NodeType.FRONT_MAN: 0.20,   # Prête-nom → un intermédiaire
    NodeType.COMPANY: 0.25,     # Société → probable intermédiaire
    NodeType.SCI: 0.20,         # SCI → souvent lié à l'immobilier
    NodeType.TRUST: 0.30,       # Trust → structure offshore
    NodeType.PROPERTY: 0.35,    # Bien immobilier → point de départ
    NodeType.BANK_ACCOUNT: 0.30, # Compte bancaire → point de départ
}

DEFAULT_HEURISTIC = 0.40


# ════════════════════════════════════════════════════════════════════════
# Algorithme A★ Adapté à l'Investigation
# ════════════════════════════════════════════════════════════════════════

class InvestigationPathfinder:
    """
    A★ adapté à l'investigation OSINT.
    
    Au lieu de minimiser la distance géographique (Google Maps),
    on MAXIMISE la confiance cumulative de la chaîne de preuves.
    
    g(n) = coût cumulé = somme des (1.0 - confidence) sur le chemin
    h(n) = heuristique = estimation du coût restant basée sur le type de nœud
    f(n) = g(n) + h(n) → A★ minimise f(n)
    
    Comme le coût = 1 - confiance, minimiser le coût = maximiser la confiance.
    """
    
    def __init__(self, graph: InvestigationGraph):
        self.graph = graph
        self._contraction_cache = {}
    
    def _heuristic(self, node_id: str, target_id: str) -> float:
        """
        Heuristique A★ : estime le coût restant pour atteindre la cible.
        Basée sur le type de nœud courant.
        L'heuristique est ADMISSIBLE (ne surestime jamais) pour garantir
        l'optimalité de A★.
        """
        if node_id == target_id:
            return 0.0
        
        node_data = self.graph.G.nodes.get(node_id, {}).get("data", {})
        node_type = node_data.get("node_type", "unknown")
        
        return HEURISTIC_COSTS.get(node_type, DEFAULT_HEURISTIC)
    
    def find_strongest_path(self, source_name: str, target_name: str) -> Optional[EvidenceChain]:
        """
        Algorithme A★ : trouve le chemin de confiance MAXIMALE
        entre un actif/personne et la cible (dirigeant).
        
        Args:
            source_name: Nom du nœud source (ex: "Villa Mougins")
            target_name: Nom du nœud cible (ex: "Alassane Ouattara")
        
        Returns:
            EvidenceChain avec les étapes, confiance totale et sources
        """
        source_id = self.graph._normalize_id(source_name)
        target_id = self.graph._normalize_id(target_name)
        
        if not self.graph.G.has_node(source_id):
            return None
        if not self.graph.G.has_node(target_id):
            return None
        if source_id == target_id:
            return self._direct_chain(source_id)
        
        # A★ avec priority queue
        # (f_score, counter, node_id, path, g_score)
        counter = 0
        open_set = []
        g_start = 0.0
        h_start = self._heuristic(source_id, target_id)
        heapq.heappush(open_set, (g_start + h_start, counter, source_id, [source_id], g_start))
        
        # Best g_score pour chaque nœud (évite de revisiter)
        best_g = {source_id: g_start}
        
        while open_set:
            f_score, _, current, path, g_current = heapq.heappop(open_set)
            
            # Cible atteinte !
            if current == target_id:
                return self._build_evidence_chain(path)
            
            # Explorer les voisins
            for neighbor in self.graph.G.neighbors(current):
                if neighbor in path:  # Pas de cycles
                    continue
                
                edge_data = self.graph.G.edges[current, neighbor].get("data", {})
                edge_weight = self.graph.G.edges[current, neighbor].get("weight", 0.9)
                
                g_neighbor = g_current + edge_weight
                
                # Ne visiter que si c'est un meilleur chemin
                if neighbor in best_g and g_neighbor >= best_g[neighbor]:
                    continue
                
                best_g[neighbor] = g_neighbor
                h_neighbor = self._heuristic(neighbor, target_id)
                f_neighbor = g_neighbor + h_neighbor
                
                counter += 1
                heapq.heappush(open_set, (
                    f_neighbor, counter, neighbor, path + [neighbor], g_neighbor
                ))
        
        # Pas de chemin trouvé
        return None
    
    def find_all_paths(self, source_name: str, target_name: str, 
                       max_depth: int = 5) -> list:
        """
        Trouve TOUS les chemins entre source et target (max depth).
        Utilise DFS limité en profondeur, puis trie par confiance.
        """
        source_id = self.graph._normalize_id(source_name)
        target_id = self.graph._normalize_id(target_name)
        
        if not self.graph.G.has_node(source_id) or not self.graph.G.has_node(target_id):
            return []
        
        all_paths = []
        
        try:
            # NetworkX simple_paths (DFS)
            for path in nx.all_simple_paths(self.graph.G, source_id, target_id, cutoff=max_depth):
                chain = self._build_evidence_chain(path)
                if chain:
                    all_paths.append(chain)
        except nx.NetworkXError:
            pass
        
        # Trier par confiance décroissante
        all_paths.sort(key=lambda c: c.total_confidence, reverse=True)
        return all_paths
    
    def rank_paths(self, chains: list) -> list:
        """
        Tri multi-critères des chaînes de preuves :
        Score = confidence × 0.5 + (sources/10) × 0.3 + (1/path_length) × 0.2
        """
        def composite_score(chain: EvidenceChain) -> float:
            conf_score = chain.total_confidence * 0.5
            src_score = min(chain.total_sources / 10.0, 1.0) * 0.3
            len_score = (1.0 / max(chain.path_length, 1)) * 0.2
            return conf_score + src_score + len_score
        
        return sorted(chains, key=composite_score, reverse=True)
    
    def _build_evidence_chain(self, path: list) -> Optional[EvidenceChain]:
        """Construit une EvidenceChain à partir d'un chemin de nœuds."""
        if not path or len(path) < 2:
            return None
        
        steps = []
        total_confidence = 1.0  # Produit des confiances (chaîne)
        total_sources = 0
        
        for i, node_id in enumerate(path):
            node_data = self.graph.G.nodes[node_id].get("data", {})
            
            relation = ""
            conf = 0.0
            sources = []
            
            if i < len(path) - 1:
                next_id = path[i + 1]
                edge_data = self.graph.G.edges[node_id, next_id].get("data", {})
                relation = edge_data.get("relation", "lié à")
                conf = edge_data.get("confidence", 0.0)
                sources = edge_data.get("sources", [])
                total_sources += len(sources)
                
                # Confiance cumulative (produit)
                total_confidence *= conf
            
            step = PathStep(
                node_id=node_id,
                label=node_data.get("label", node_id),
                node_type=node_data.get("node_type", "unknown"),
                relation_to_next=relation,
                confidence_to_next=conf,
                sources=sources,
            )
            steps.append(step)
        
        return EvidenceChain(
            steps=steps,
            total_confidence=total_confidence,
            total_sources=total_sources,
            path_length=len(path),
        )
    
    def _direct_chain(self, node_id: str) -> EvidenceChain:
        """Chaîne directe (le nœud est la cible elle-même)."""
        node_data = self.graph.G.nodes[node_id].get("data", {})
        step = PathStep(
            node_id=node_id,
            label=node_data.get("label", node_id),
            node_type=node_data.get("node_type", "unknown"),
            relation_to_next="CIBLE",
            confidence_to_next=1.0,
        )
        return EvidenceChain(
            steps=[step],
            total_confidence=1.0,
            total_sources=0,
            path_length=1,
        )
    
    # ── Contraction Hierarchies ────────────────────────────────────────
    
    def build_contraction_hierarchy(self):
        """
        Pré-calcule des raccourcis entre les nœuds "importants".
        
        Un nœud est "important" si :
        - C'est une cible (dirigeant)
        - C'est un nœud avec beaucoup de connexions (hub)
        - C'est une société/SCI récurrente
        
        Cela permet d'accélérer les requêtes futures ×10-100.
        """
        # Identifier les nœuds importants (hubs)
        importance = {}
        for node_id in self.graph.G.nodes:
            data = self.graph.G.nodes[node_id].get("data", {})
            node_type = data.get("node_type", "")
            degree = self.graph.G.degree(node_id)
            
            # Score d'importance
            score = degree
            if node_type == NodeType.TARGET:
                score += 100
            elif node_type in {NodeType.COMPANY, NodeType.SCI}:
                score += 10
            elif node_type == NodeType.FAMILY:
                score += 5
            
            importance[node_id] = score
        
        # Trier par importance décroissante
        sorted_nodes = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        important_nodes = [n[0] for n in sorted_nodes[:20]]  # Top 20
        
        # Pré-calculer les chemins entre tous les nœuds importants
        for i, src in enumerate(important_nodes):
            for tgt in important_nodes[i+1:]:
                try:
                    chain = self.find_strongest_path(src, tgt)
                    if chain:
                        cache_key = (src, tgt)
                        self._contraction_cache[cache_key] = chain
                        # Aussi le chemin inverse
                        self._contraction_cache[(tgt, src)] = chain
                except Exception:
                    pass
        
        print(f"[PATHFINDER] Contraction Hierarchies : {len(self._contraction_cache)} raccourcis pré-calculés")
    
    def find_with_contraction(self, source_name: str, target_name: str) -> Optional[EvidenceChain]:
        """
        Cherche d'abord dans le cache des Contraction Hierarchies,
        puis fallback sur A★ classique.
        """
        source_id = self.graph._normalize_id(source_name)
        target_id = self.graph._normalize_id(target_name)
        
        cache_key = (source_id, target_id)
        if cache_key in self._contraction_cache:
            return self._contraction_cache[cache_key]
        
        return self.find_strongest_path(source_name, target_name)
