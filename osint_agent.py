# -*- coding: utf-8 -*-
"""
OSINT Agent v4 - Tool API for ReAct LLM Agent
"""

import time
import json
from typing import Optional

from investigation_graph import (
    InvestigationGraph, NodeType, EvidenceType,
    CONFIDENCE_WEIGHTS, Source
)
from entity_resolver import (
    PersonResolver, CorporateResolver, PropertyResolver, FuzzyNameMatcher
)
from pathfinder import InvestigationPathfinder

_sessions = {}
CACHE = {}
CACHE_TTL = 3600


def get_or_create_session(session_id="default"):
    if session_id not in _sessions:
        _sessions[session_id] = {
            "graph": InvestigationGraph(),
            "created_at": time.time(),
            "steps": [],
        }
    return _sessions[session_id]


def reset_session(session_id="default"):
    if session_id in _sessions:
        del _sessions[session_id]


# === TOOL 1: Search Person ===

def search_person(name, country="", context="", session_id="default"):
    """Search person: Wikidata + DuckDuckGo."""
    resolver = PersonResolver()
    session = get_or_create_session(session_id)

    wikidata_result = resolver.search_wikidata(name)

    queries = []
    if context:
        queries.append(f'"{name}" {context}')
    queries.extend([
        f'"{name}" famille epouse fils fille wife children',
        f'"{name}" {country} biographie parcours',
    ])

    web_results = []
    for q in queries[:2]:
        results = resolver.search_duckduckgo(q, max_results=3)
        web_results.extend(results)

    if wikidata_result.get("found"):
        graph = session["graph"]
        node_type = NodeType.TARGET if not graph.get_node_count() else NodeType.ASSOCIATE
        graph.add_person(name, node_type=node_type, country=country,
                        description=wikidata_result.get("description", ""))

        for rel in wikidata_result.get("relations", []):
            rel_name = rel["name"]
            relation = rel["relation"]
            if rel_name and rel_name != "Inconnu":
                graph.add_person(rel_name, node_type=NodeType.FAMILY, country=country)
                graph.add_relation(
                    name, rel_name, relation,
                    confidence=CONFIDENCE_WEIGHTS[EvidenceType.WIKIDATA],
                    evidence_type=EvidenceType.WIKIDATA,
                    sources=[Source(
                        url=wikidata_result["source_url"],
                        title=f"Wikidata - {name}",
                        evidence_type=EvidenceType.WIKIDATA,
                    )]
                )

    session["steps"].append({
        "action": "SEARCH_PERSON",
        "args": {"name": name, "country": country},
        "timestamp": time.time(),
        "results_count": len(web_results) + len(wikidata_result.get("relations", [])),
    })

    return {
        "wikidata": wikidata_result,
        "web_results": web_results,
        "name_searched": name,
        "graph_updated": wikidata_result.get("found", False),
    }


# === TOOL 2: Search Company ===

def search_company(name, jurisdiction="", session_id="default"):
    """Search companies: Pappers + OpenCorporates."""
    resolver = CorporateResolver()
    session = get_or_create_session(session_id)
    graph = session["graph"]

    pappers_result = resolver.search_pappers(name)
    oc_result = resolver.search_opencorporates(name, jurisdiction)

    all_companies = (pappers_result.get("companies", []) +
                     oc_result.get("companies", []))

    for company in all_companies:
        company_name = company.get("name", "")
        if not company_name:
            continue

        company_type_str = company.get("type", "").upper()
        if "SCI" in company_type_str:
            node_type = NodeType.SCI
        elif "TRUST" in company_type_str or "FOUNDATION" in company_type_str:
            node_type = NodeType.TRUST
        else:
            node_type = NodeType.COMPANY

        graph.add_entity(
            company_name, node_type=node_type,
            siren=company.get("siren", company.get("company_number", "")),
            country=company.get("jurisdiction", ""),
            address=company.get("address", ""),
        )

        source_url = company.get("source_url", "")
        confidence = pappers_result.get("confidence", 0.5)

        graph.add_person(name, node_type=NodeType.ASSOCIATE)
        graph.add_relation(
            name, company_name,
            relation=company.get("role", "dirigeant/associe"),
            confidence=confidence,
            evidence_type=EvidenceType.REGISTRY,
            sources=[Source(url=source_url, title=company_name,
                           evidence_type=EvidenceType.REGISTRY)]
        )

    session["steps"].append({
        "action": "SEARCH_COMPANY",
        "args": {"name": name, "jurisdiction": jurisdiction},
        "timestamp": time.time(),
        "results_count": len(all_companies),
    })

    return {
        "pappers": pappers_result,
        "opencorporates": oc_result,
        "total_companies": len(all_companies),
        "name_searched": name,
    }


# === TOOL 3: Search Property ===

def search_property(name, city="", address="", session_id="default"):
    """Search properties: DVF + DuckDuckGo."""
    resolver = PropertyResolver()
    session = get_or_create_session(session_id)

    dvf_result = {"found": False, "mutations": []}
    if city:
        dvf_result = resolver.search_dvf(commune=city)
    elif address:
        dvf_result = resolver.search_dvf(address=address)

    web_results = []
    if city:
        web_results = resolver.search_property_duckduckgo(name, city)

    gps = None
    if address:
        gps = resolver.geocode_address(address)
    elif city:
        gps = resolver.geocode_address(city)

    session["steps"].append({
        "action": "SEARCH_PROPERTY",
        "args": {"name": name, "city": city, "address": address},
        "timestamp": time.time(),
        "results_count": len(dvf_result.get("mutations", [])) + len(web_results),
    })

    return {
        "dvf": dvf_result,
        "web_results": web_results,
        "gps": gps,
        "name_searched": name,
        "city": city,
    }


# === TOOL 4: Search OCCRP Aleph ===

def search_aleph(name, session_id="default"):
    """Search OCCRP Aleph: Panama Papers, Pandora Papers."""
    resolver = CorporateResolver()
    session = get_or_create_session(session_id)
    graph = session["graph"]

    result = resolver.search_aleph(name)

    for item in result.get("results", []):
        item_name = item.get("name", "")
        if not item_name:
            continue

        schema = item.get("schema", "")
        if schema in ("Company", "Organization", "LegalEntity"):
            graph.add_entity(item_name, node_type=NodeType.COMPANY,
                           country=", ".join(item.get("countries", [])))
        else:
            graph.add_person(item_name, node_type=NodeType.ASSOCIATE,
                           country=", ".join(item.get("countries", [])))

        matcher = FuzzyNameMatcher()
        existing_persons = [p["label"] for p in graph.get_all_persons()]
        match_result = matcher.find_best_match(item_name, existing_persons)

        if match_result:
            source_url = item.get("source_url", "")
            datasets = ", ".join(item.get("datasets", []))
            graph.add_relation(
                match_result["candidate"], item_name,
                relation=f"mentionne dans {datasets}",
                confidence=CONFIDENCE_WEIGHTS[EvidenceType.INVESTIGATION],
                evidence_type=EvidenceType.INVESTIGATION,
                sources=[Source(url=source_url, title=f"OCCRP - {datasets}",
                               evidence_type=EvidenceType.INVESTIGATION)]
            )

    session["steps"].append({
        "action": "SEARCH_ALEPH",
        "args": {"name": name},
        "timestamp": time.time(),
        "results_count": len(result.get("results", [])),
    })

    return result


# === TOOL 5: Search Images ===

def search_images_tool(query, max_results=4, session_id="default"):
    """Search images via DuckDuckGo."""
    resolver = PersonResolver()
    images = resolver.search_images(query, max_results)

    session = get_or_create_session(session_id)
    session["steps"].append({
        "action": "SEARCH_IMAGES",
        "args": {"query": query},
        "timestamp": time.time(),
        "results_count": len(images),
    })

    return {"images": images, "query": query}


# === TOOL 6: Graph Manipulation ===

def graph_add_node(name, node_type, country="", description="",
                   address="", siren="", session_id="default"):
    """Add a node to the investigation graph."""
    session = get_or_create_session(session_id)
    graph = session["graph"]

    entity_types = {NodeType.COMPANY, NodeType.SCI, NodeType.TRUST, NodeType.PROPERTY}
    if node_type in entity_types:
        node_id = graph.add_entity(name, node_type=node_type, country=country,
                                   address=address, siren=siren, description=description)
    else:
        node_id = graph.add_person(name, node_type=node_type, country=country,
                                  description=description)

    return {"success": True, "node_id": node_id, "total_nodes": graph.get_node_count()}


def graph_add_relation(source, target, relation, confidence=0.5,
                       evidence_type="speculatif", source_url="",
                       session_id="default"):
    """Add a relation (edge) to the graph."""
    session = get_or_create_session(session_id)
    graph = session["graph"]

    sources = []
    if source_url:
        sources.append(Source(url=source_url, evidence_type=evidence_type))

    success = graph.add_relation(source, target, relation, confidence, evidence_type, sources)
    return {"success": success, "total_edges": graph.get_edge_count()}


# === TOOL 7: A* Pathfinding ===

def graph_pathfind(source, target, session_id="default"):
    """Run A* pathfinder for max-confidence path."""
    session = get_or_create_session(session_id)
    graph = session["graph"]

    pathfinder = InvestigationPathfinder(graph)
    best = pathfinder.find_strongest_path(source, target)
    all_paths = pathfinder.find_all_paths(source, target, max_depth=5)
    ranked = pathfinder.rank_paths(all_paths)

    return {
        "best_path": best.to_dict() if best else None,
        "best_narrative": best.to_narrative() if best else "No path found.",
        "all_paths": [p.to_dict() for p in ranked[:5]],
        "total_paths_found": len(all_paths),
    }


# === TOOL 8: Graph Export ===

def graph_export(session_id="default"):
    """Export graph as JSON for frontend (react-force-graph)."""
    session = get_or_create_session(session_id)
    graph = session["graph"]

    return {
        "graph": graph.export_for_frontend(),
        "summary": graph.summary(),
        "steps_count": len(session["steps"]),
    }


def graph_summary(session_id="default"):
    """Text summary of the graph for the LLM."""
    session = get_or_create_session(session_id)
    return session["graph"].summary()


# === FULL INVESTIGATION (Fallback without WebGPU) ===

def investigate_full(leader_name, country, target_city="", session_id="default"):
    """Full automated investigation pipeline (fallback if no WebGPU)."""
    reset_session(session_id)

    print(f"\n[OSINT v4] === INVESTIGATION: {leader_name} -> {target_city} ===")

    # Phase 1: Genealogy
    print("[OSINT v4] Phase 1: Building genealogy tree...")
    search_person(leader_name, country, session_id=session_id)

    session = get_or_create_session(session_id)
    graph = session["graph"]
    graph.add_person(leader_name, node_type=NodeType.TARGET, country=country)

    persons = graph.get_all_persons()
    print(f"[OSINT v4]   -> {len(persons)} persons identified")

    # Phase 2: Companies
    print("[OSINT v4] Phase 2: Searching companies...")
    for person in persons[:6]:
        search_company(person["label"], session_id=session_id)

    entities = graph.get_all_entities()
    print(f"[OSINT v4]   -> {len(entities)} companies found")

    # Phase 3: OCCRP Aleph
    print("[OSINT v4] Phase 3: Searching OCCRP...")
    search_aleph(leader_name, session_id=session_id)

    # Phase 4: Properties
    if target_city:
        print(f"[OSINT v4] Phase 4: Searching properties in {target_city}...")
        for person in persons[:4]:
            search_property(person["label"], city=target_city, session_id=session_id)

    # Phase 5: Images
    if target_city:
        print("[OSINT v4] Phase 5: Searching images...")
        search_images_tool(
            f"{leader_name} {target_city} villa residence",
            session_id=session_id
        )

    # Phase 6: Pathfinding
    print("[OSINT v4] Phase 6: A* Pathfinding...")
    properties = graph.get_all_properties()
    evidence_chains = []
    for prop in properties:
        path_result = graph_pathfind(prop["label"], leader_name, session_id=session_id)
        if path_result.get("best_path"):
            evidence_chains.append(path_result["best_path"])

    export = graph_export(session_id=session_id)

    print(f"[OSINT v4] === DONE: {graph.get_node_count()} nodes, {graph.get_edge_count()} edges ===\n")

    return {
        "graph": export["graph"],
        "summary": export["summary"],
        "evidence_chains": evidence_chains,
        "total_steps": len(session["steps"]),
        "leader": leader_name,
        "country": country,
        "target_city": target_city,
    }
