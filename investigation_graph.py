"""
Investigation Graph v4 — Graphe Pondéré d'Investigation OSINT
=============================================================
Graphe NetworkX avec nœuds typés et arêtes de confiance.
Chaque lien a un poids (confiance) et des sources vérifiables.
Le graphe est sérialisable en JSON pour le frontend (react-force-graph).
"""

import networkx as nx
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import time


# ════════════════════════════════════════════════════════════════════════
# Poids de confiance par type de source
# ════════════════════════════════════════════════════════════════════════

class EvidenceType(str, Enum):
    """Classification des sources par fiabilité."""
    JUDICIAL = "judiciaire"           # Décision de justice, registre officiel
    REGISTRY = "registre"             # Pappers, SIREN, OpenCorporates
    DVF = "dvf"                       # Mutations foncières (data.gouv.fr)
    INVESTIGATION = "investigation"   # OCCRP, ICIJ, Panama Papers
    PRESS_INVESTIGATION = "presse_investigation"  # Mediapart, Africa Intelligence
    PRESS_GENERAL = "presse"          # Le Monde, Reuters
    WIKIDATA = "wikidata"             # Wikidata SPARQL
    OSINT_INFERRED = "osint"          # Même nom de famille, même adresse
    SPECULATIVE = "spéculatif"        # DuckDuckGo non vérifié


CONFIDENCE_WEIGHTS = {
    EvidenceType.JUDICIAL: 0.95,
    EvidenceType.REGISTRY: 0.85,
    EvidenceType.DVF: 0.80,
    EvidenceType.INVESTIGATION: 0.70,
    EvidenceType.PRESS_INVESTIGATION: 0.60,
    EvidenceType.WIKIDATA: 0.75,
    EvidenceType.PRESS_GENERAL: 0.40,
    EvidenceType.OSINT_INFERRED: 0.25,
    EvidenceType.SPECULATIVE: 0.10,
}


# ════════════════════════════════════════════════════════════════════════
# Data Classes pour les nœuds et arêtes
# ════════════════════════════════════════════════════════════════════════

class NodeType(str, Enum):
    TARGET = "cible"
    FAMILY = "famille"
    ASSOCIATE = "associé"
    FRONT_MAN = "prête-nom"
    COMPANY = "société"
    SCI = "SCI"
    TRUST = "trust"
    PROPERTY = "bien_immobilier"
    BANK_ACCOUNT = "compte_bancaire"


@dataclass
class Source:
    """Une source de preuve vérifiable."""
    url: str
    title: str = ""
    snippet: str = ""
    evidence_type: str = "spéculatif"
    date: str = ""
    
    def to_dict(self):
        return asdict(self)


@dataclass 
class NodeData:
    """Métadonnées d'un nœud du graphe."""
    node_type: str
    label: str
    country: str = ""
    address: str = ""
    siren: str = ""
    description: str = ""
    gps: Optional[dict] = None
    images: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self):
        d = asdict(self)
        return d


@dataclass
class EdgeData:
    """Métadonnées d'une arête (relation) du graphe."""
    relation: str
    confidence: float
    evidence_type: str
    sources: list = field(default_factory=list)
    discovered_at: float = field(default_factory=time.time)
    
    def to_dict(self):
        d = asdict(self)
        return d


# ════════════════════════════════════════════════════════════════════════
# Graphe d'Investigation Principal
# ════════════════════════════════════════════════════════════════════════

class InvestigationGraph:
    """
    Graphe pondéré pour investigation OSINT.
    
    Utilise NetworkX DiGraph (dirigé) pour modéliser :
    - Les personnes, sociétés, biens immobiliers comme nœuds
    - Les relations (épouse, dirigeant, propriétaire) comme arêtes pondérées
    - La confiance de chaque lien basée sur les sources
    
    Le poids des arêtes = 1.0 - confidence (pour que A★ minimise le coût
    = maximise la confiance sur le chemin).
    """
    
    def __init__(self):
        self.G = nx.DiGraph()
        self._node_counter = 0
    
    def _normalize_id(self, name: str) -> str:
        """Normalise un nom en identifiant unique."""
        return name.strip().lower().replace("  ", " ")
    
    # ── Nœuds ──────────────────────────────────────────────────────────
    
    def add_person(self, name: str, node_type: str = NodeType.FAMILY,
                   country: str = "", description: str = "",
                   **kwargs) -> str:
        """Ajoute un nœud personne au graphe."""
        node_id = self._normalize_id(name)
        
        if self.G.has_node(node_id):
            # Mettre à jour les métadonnées si le nœud existe déjà
            existing = self.G.nodes[node_id].get("data", {})
            if description and not existing.get("description"):
                existing["description"] = description
            return node_id
        
        data = NodeData(
            node_type=node_type,
            label=name,
            country=country,
            description=description,
            **kwargs
        )
        
        self.G.add_node(node_id, data=data.to_dict(), label=name)
        self._node_counter += 1
        return node_id
    
    def add_entity(self, name: str, node_type: str = NodeType.COMPANY,
                   siren: str = "", country: str = "", 
                   address: str = "", **kwargs) -> str:
        """Ajoute un nœud entité (société, SCI, trust, bien immobilier)."""
        node_id = self._normalize_id(name)
        
        if self.G.has_node(node_id):
            existing = self.G.nodes[node_id].get("data", {})
            if siren and not existing.get("siren"):
                existing["siren"] = siren
            if address and not existing.get("address"):
                existing["address"] = address
            return node_id
        
        data = NodeData(
            node_type=node_type,
            label=name,
            siren=siren,
            country=country,
            address=address,
            **kwargs
        )
        
        self.G.add_node(node_id, data=data.to_dict(), label=name)
        self._node_counter += 1
        return node_id
    
    def add_property(self, name: str, address: str = "", 
                     gps: dict = None, images: list = None,
                     price: str = "", **kwargs) -> str:
        """Ajoute un bien immobilier au graphe."""
        node_id = self._normalize_id(name)
        
        metadata = kwargs.pop("metadata", {})
        if price:
            metadata["price"] = price
        
        if self.G.has_node(node_id):
            existing = self.G.nodes[node_id].get("data", {})
            if images:
                existing_images = existing.get("images", [])
                existing_images.extend(images)
                existing["images"] = existing_images
            return node_id
        
        data = NodeData(
            node_type=NodeType.PROPERTY,
            label=name,
            address=address,
            gps=gps,
            images=images or [],
            metadata=metadata,
            **kwargs
        )
        
        self.G.add_node(node_id, data=data.to_dict(), label=name)
        self._node_counter += 1
        return node_id
    
    # ── Arêtes ─────────────────────────────────────────────────────────
    
    def add_relation(self, source_name: str, target_name: str,
                     relation: str, confidence: float = 0.5,
                     evidence_type: str = EvidenceType.SPECULATIVE,
                     sources: list = None) -> bool:
        """
        Ajoute une relation (arête) entre deux nœuds.
        
        Le poids de l'arête = 1.0 - confidence, pour que A★ cherche
        le chemin de coût MINIMAL = confiance MAXIMALE.
        
        Si l'arête existe déjà, la confiance est mise à jour au maximum
        et les sources sont fusionnées.
        """
        source_id = self._normalize_id(source_name)
        target_id = self._normalize_id(target_name)
        
        if not self.G.has_node(source_id) or not self.G.has_node(target_id):
            return False
        
        edge_sources = []
        if sources:
            for s in sources:
                if isinstance(s, Source):
                    edge_sources.append(s.to_dict())
                elif isinstance(s, dict):
                    edge_sources.append(s)
                else:
                    edge_sources.append({"url": str(s)})
        
        if self.G.has_edge(source_id, target_id):
            # Mettre à jour : prendre la confiance la plus haute
            existing = self.G.edges[source_id, target_id]
            existing_data = existing.get("data", {})
            old_conf = existing_data.get("confidence", 0)
            new_conf = max(old_conf, confidence)
            existing_data["confidence"] = new_conf
            existing_data["sources"] = existing_data.get("sources", []) + edge_sources
            existing["weight"] = 1.0 - new_conf
        else:
            edge_data = EdgeData(
                relation=relation,
                confidence=confidence,
                evidence_type=evidence_type,
                sources=edge_sources,
            )
            
            self.G.add_edge(
                source_id, target_id,
                weight=1.0 - confidence,
                data=edge_data.to_dict(),
                label=relation
            )
        
        # Ajouter aussi l'arête inverse (graphe non-dirigé pour le pathfinding)
        if not self.G.has_edge(target_id, source_id):
            reverse_relation = self._invert_relation(relation)
            edge_data_rev = EdgeData(
                relation=reverse_relation,
                confidence=confidence,
                evidence_type=evidence_type,
                sources=edge_sources,
            )
            self.G.add_edge(
                target_id, source_id,
                weight=1.0 - confidence,
                data=edge_data_rev.to_dict(),
                label=reverse_relation
            )
        
        return True
    
    def _invert_relation(self, relation: str) -> str:
        """Inverse une relation pour l'arête retour."""
        inversions = {
            "épouse": "époux",
            "époux": "épouse",
            "fils": "père/mère",
            "fille": "père/mère",
            "père": "fils/fille",
            "mère": "fils/fille",
            "frère": "frère/sœur",
            "sœur": "frère/sœur",
            "beau-frère": "beau-frère/belle-sœur",
            "neveu": "oncle/tante",
            "dirigeant": "société de",
            "actionnaire": "actionnaire de",
            "bénéficiaire effectif": "contrôlé par",
            "propriétaire": "appartient à",
            "associé": "associé",
        }
        return inversions.get(relation.lower(), f"lié à ({relation})")
    
    # ── Requêtes ───────────────────────────────────────────────────────
    
    def get_all_persons(self) -> list:
        """Retourne tous les nœuds de type personne."""
        persons = []
        person_types = {NodeType.TARGET, NodeType.FAMILY, NodeType.ASSOCIATE, NodeType.FRONT_MAN}
        for node_id in self.G.nodes:
            data = self.G.nodes[node_id].get("data", {})
            if data.get("node_type") in person_types:
                persons.append({
                    "id": node_id,
                    "label": data.get("label", node_id),
                    "type": data.get("node_type"),
                    "country": data.get("country", ""),
                })
        return persons
    
    def get_all_entities(self) -> list:
        """Retourne tous les nœuds entité (sociétés, SCI, trusts)."""
        entities = []
        entity_types = {NodeType.COMPANY, NodeType.SCI, NodeType.TRUST}
        for node_id in self.G.nodes:
            data = self.G.nodes[node_id].get("data", {})
            if data.get("node_type") in entity_types:
                entities.append({
                    "id": node_id,
                    "label": data.get("label", node_id),
                    "type": data.get("node_type"),
                    "siren": data.get("siren", ""),
                })
        return entities
    
    def get_all_properties(self) -> list:
        """Retourne tous les biens immobiliers."""
        props = []
        for node_id in self.G.nodes:
            data = self.G.nodes[node_id].get("data", {})
            if data.get("node_type") == NodeType.PROPERTY:
                props.append({
                    "id": node_id,
                    "label": data.get("label", node_id),
                    "address": data.get("address", ""),
                    "gps": data.get("gps"),
                    "images": data.get("images", []),
                    "price": data.get("metadata", {}).get("price", ""),
                })
        return props
    
    def get_neighbors(self, name: str) -> list:
        """Retourne les voisins directs d'un nœud."""
        node_id = self._normalize_id(name)
        if not self.G.has_node(node_id):
            return []
        
        neighbors = []
        for neighbor_id in self.G.neighbors(node_id):
            edge_data = self.G.edges[node_id, neighbor_id].get("data", {})
            node_data = self.G.nodes[neighbor_id].get("data", {})
            neighbors.append({
                "id": neighbor_id,
                "label": node_data.get("label", neighbor_id),
                "type": node_data.get("node_type", "unknown"),
                "relation": edge_data.get("relation", "lié à"),
                "confidence": edge_data.get("confidence", 0.0),
            })
        return neighbors
    
    def get_node_count(self) -> int:
        return self.G.number_of_nodes()
    
    def get_edge_count(self) -> int:
        return self.G.number_of_edges()
    
    # ── Export pour le frontend ────────────────────────────────────────
    
    def export_for_frontend(self) -> dict:
        """
        Exporte le graphe en format JSON compatible avec react-force-graph.
        
        Format :
        {
            "nodes": [{"id": ..., "label": ..., "type": ..., "color": ..., "size": ...}],
            "links": [{"source": ..., "target": ..., "label": ..., "confidence": ..., "color": ...}]
        }
        """
        # Couleurs par type de nœud
        type_colors = {
            NodeType.TARGET: "#ff3333",        # Rouge vif — cible principale
            NodeType.FAMILY: "#ff9933",         # Orange — famille
            NodeType.ASSOCIATE: "#ffcc33",      # Jaune doré — associés
            NodeType.FRONT_MAN: "#cc33ff",      # Violet — prête-noms
            NodeType.COMPANY: "#3399ff",        # Bleu — sociétés
            NodeType.SCI: "#33ccff",            # Cyan — SCI
            NodeType.TRUST: "#9933ff",          # Violet foncé — trusts
            NodeType.PROPERTY: "#33ff99",       # Vert — biens immobiliers
            NodeType.BANK_ACCOUNT: "#ff33cc",   # Rose — comptes bancaires
        }
        
        type_sizes = {
            NodeType.TARGET: 20,
            NodeType.FAMILY: 12,
            NodeType.ASSOCIATE: 10,
            NodeType.FRONT_MAN: 10,
            NodeType.COMPANY: 14,
            NodeType.SCI: 12,
            NodeType.TRUST: 12,
            NodeType.PROPERTY: 16,
            NodeType.BANK_ACCOUNT: 10,
        }
        
        nodes = []
        for node_id in self.G.nodes:
            data = self.G.nodes[node_id].get("data", {})
            node_type = data.get("node_type", "unknown")
            nodes.append({
                "id": node_id,
                "label": data.get("label", node_id),
                "type": node_type,
                "color": type_colors.get(node_type, "#666666"),
                "size": type_sizes.get(node_type, 8),
                "country": data.get("country", ""),
                "address": data.get("address", ""),
                "images": data.get("images", []),
                "description": data.get("description", ""),
            })
        
        links = []
        seen_edges = set()
        for source_id, target_id in self.G.edges:
            edge_key = tuple(sorted([source_id, target_id]))
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            
            edge_data = self.G.edges[source_id, target_id].get("data", {})
            confidence = edge_data.get("confidence", 0.0)
            
            # Couleur de l'arête basée sur la confiance
            if confidence >= 0.8:
                link_color = "rgba(51, 255, 51, 0.8)"    # Vert — haute confiance
            elif confidence >= 0.5:
                link_color = "rgba(255, 204, 51, 0.6)"   # Jaune — moyenne
            elif confidence >= 0.3:
                link_color = "rgba(255, 153, 51, 0.4)"   # Orange — faible
            else:
                link_color = "rgba(255, 51, 51, 0.3)"    # Rouge — spéculatif
            
            links.append({
                "source": source_id,
                "target": target_id,
                "label": edge_data.get("relation", ""),
                "confidence": confidence,
                "evidence_type": edge_data.get("evidence_type", ""),
                "color": link_color,
                "width": max(1, confidence * 5),
                "sources_count": len(edge_data.get("sources", [])),
            })
        
        return {
            "nodes": nodes,
            "links": links,
            "stats": {
                "total_nodes": len(nodes),
                "total_links": len(links),
                "persons": sum(1 for n in nodes if n["type"] in 
                              {NodeType.TARGET, NodeType.FAMILY, NodeType.ASSOCIATE, NodeType.FRONT_MAN}),
                "entities": sum(1 for n in nodes if n["type"] in 
                              {NodeType.COMPANY, NodeType.SCI, NodeType.TRUST}),
                "properties": sum(1 for n in nodes if n["type"] == NodeType.PROPERTY),
            }
        }
    
    def to_json(self) -> str:
        """Sérialise le graphe complet en JSON."""
        return json.dumps(self.export_for_frontend(), ensure_ascii=False, indent=2)
    
    def summary(self) -> str:
        """Résumé textuel du graphe pour le LLM."""
        lines = [f"Graphe d'investigation : {self.get_node_count()} nœuds, {self.get_edge_count()} arêtes"]
        
        for node_id in self.G.nodes:
            data = self.G.nodes[node_id].get("data", {})
            label = data.get("label", node_id)
            ntype = data.get("node_type", "?")
            neighbors = self.get_neighbors(label)
            if neighbors:
                rels = ", ".join([f"{n['label']} ({n['relation']}, conf:{n['confidence']:.0%})" 
                                 for n in neighbors[:5]])
                lines.append(f"  [{ntype}] {label} -> {rels}")
            else:
                lines.append(f"  [{ntype}] {label} (isolé)")
        
        return "\n".join(lines)
