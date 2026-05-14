"""
JetWatch Africa — Couche Intelligence : CrewAI Investigation Task Force

Remplace les pipelines linéaires de investigator_osint.py et classifier.py
par une équipe d'agents IA autonomes capables de raisonner, d'adapter leurs
recherches, et de croiser les données de manière itérative.

Architecture :
  Agent 1 (Traqueur OSINT)    → collecte adaptative des sources ouvertes
  Agent 2 (Cartographe)       → construit le graphe des connexions
  Agent 3 (Procureur)         → synthèse + rapport markdown + score de risque

Le modèle LLM est configurable via la variable d'environnement CREWAI_LLM.
Recommandé : groq/llama-3.1-70b-versatile (gratuit, rapide, puissant)
"""

import os
import json
import re
from datetime import datetime
from typing import Optional

# ── Détection de la disponibilité de CrewAI ──────────────────────────────────
try:
    from crewai import Agent, Task, Crew, Process, LLM
    from crewai.tools import tool
    import requests
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    print("[CrewAI] Package non installé — fallback vers investigator_osint disponible.")

# ── Configuration LLM (Groq par défaut — gratuit et rapide) ──────────────────
def get_llm(model_id: str = "groq/llama-3.3-70b-versatile"):
    """
    Retourne la configuration LLM pour CrewAI.
    Utilise dynamiquement le model_id sélectionné par l'utilisateur.
    Priorité : Groq (avec model_id) > OpenAI > Anthropic > Ollama local
    """
    groq_key = os.getenv("GROQ_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if groq_key:
        # Utilise le modèle choisi par l'utilisateur via le frontend
        print(f"[CrewAI] Modèle sélectionné : {model_id}")
        return LLM(
            model=model_id,
            api_key=groq_key,
            temperature=0.1,
            max_tokens=4000,
        )
    elif openai_key:
        return LLM(
            model="gpt-4o-mini",
            api_key=openai_key,
            temperature=0.1,
            max_tokens=4000,
        )
    elif anthropic_key:
        return LLM(
            model="claude-3-haiku-20240307",
            api_key=anthropic_key,
            temperature=0.1,
            max_tokens=4000,
        )
    else:
        # Ollama local (nécessite Ollama installé)
        return LLM(
            model="ollama/llama3.1",
            base_url="http://localhost:11434",
            temperature=0.1,
        )


# ── Résultat d'une investigation ──────────────────────────────────────────────
class InvestigationResult:
    def __init__(self):
        self.osint_report: str = ""
        self.graph_json: dict = {"nodes": [], "edges": []}
        self.final_report: str = ""
        self.sources: list = []
        self.risk_score: int = 0
        self.error: Optional[str] = None


@tool("Search Internet")
def search_internet(query: str) -> str:
    """Useful to search the internet about a given topic and return relevant results."""
    serper_key = os.getenv("SERPER_API_KEY")
    if serper_key:
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query})
        headers = {
            'X-API-KEY': serper_key,
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(url, headers=headers, data=payload)
            results = response.json()
            if 'organic' in results:
                return "\\n".join([f"Title: {r.get('title')}\\nSnippet: {r.get('snippet')}\\nLink: {r.get('link')}\\n" for r in results['organic'][:5]])
            return str(results)
        except Exception as e:
            return f"Error searching internet: {str(e)}"
    
    # Fallback to duckduckgo_search library since it's in requirements.txt
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=5)
        return "\\n".join([f"Title: {r.get('title')}\\nSnippet: {r.get('body')}\\nLink: {r.get('href')}\\n" for r in results])
    except Exception as e:
        return f"Error with DuckDuckGo fallback: {str(e)}"

def _build_tools():
    """Construit la liste d'outils selon les clés disponibles."""
    return [search_internet]


# ── Extraction des URLs sources depuis le rapport OSINT ──────────────────────
def _extract_sources_from_report(report_text: str) -> list:
    """Extrait les URLs citées dans le rapport de l'Agent OSINT."""
    url_pattern = r'https?://[^\s\)\]\,\"]+'
    urls = re.findall(url_pattern, report_text)
    return list(set(urls))  # Dédoublonnage


def _extract_graph_json(raw_output: str) -> dict:
    """Extrait le JSON du graphe depuis la sortie brute de l'Agent Cartographe."""
    # Cherche le bloc JSON entre ``` ou directement
    json_match = re.search(r'\{[\s\S]*"nodes"[\s\S]*"edges"[\s\S]*\}', raw_output)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Retourne un graphe minimal en cas d'échec
    return {
        "nodes": [{"id": "dirigeant", "name": "Inconnu", "category": "racine", "degree": 0}],
        "edges": [],
        "error": "Impossible de parser le graphe JSON"
    }


def _extract_risk_score(report_text: str) -> int:
    """Extrait le score de risque depuis le rapport final."""
    # Cherche des patterns comme "Score : 7/10" ou "7/10" ou "risque: 7"
    patterns = [
        r'score\s*(?:de\s*risque)?\s*[:=]\s*(\d+)\s*(?:/\s*10)?',
        r'(\d+)\s*/\s*10',
        r'score\s*[:=]\s*(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, report_text, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            return min(10, max(0, score))
    return 5  # Score par défaut


# ══════════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE — run_investigation_crew()
# ══════════════════════════════════════════════════════════════════════════════

def run_investigation_crew(
    dirigeant: str,
    pays: str,
    destination: str,
    date_vol: str,
    duree_sejour: str = "Inconnue",
    context_extra: str = "",
    status_updater = None,
    model_id: str = "groq/llama-3.3-70b-versatile",
) -> InvestigationResult:
    """
    Lance l'équipe d'investigation CrewAI sur un dirigeant/vol suspect.

    Args:
        dirigeant     : Nom du chef d'État (ex: "Muhammadu Buhari")
        pays          : Pays d'origine (ex: "Nigeria")
        destination   : Aéroport ou ville de destination (ex: "Dubaï / DXB")
        date_vol      : Date du vol au format YYYY-MM-DD
        duree_sejour  : Durée estimée du séjour (ex: "3.5 heures")
        context_extra : Informations supplémentaires (callsign, ICAO, etc.)
        status_updater: Fonction de callback pour le statut (agent_id, message)

    Returns:
        InvestigationResult avec rapport OSINT, graphe JSON, rapport final et score
    """
    result = InvestigationResult()

    if not CREWAI_AVAILABLE:
        result.error = (
            "CrewAI non installé. Exécutez : pip install crewai crewai-tools"
        )
        return result

    llm = get_llm(model_id)
    tools = _build_tools()

    # ── AGENT 1 : Traqueur OSINT ──────────────────────────────────────────────
    osint_agent = Agent(
        role="Expert en Investigation OSINT et Journalisme d'Investigation",
        goal=(
            f"Collecter toutes les preuves publiques disponibles sur {dirigeant} "
            f"({pays}) concernant son voyage vers {destination} le {date_vol}."
        ),
        backstory="""
        Vous êtes un journaliste d'investigation de renommée internationale,
        spécialisé en biens mal acquis et transparence politique africaine.
        Vous avez contribué aux Panama Papers, aux Pandora Papers, et travaillé
        pour OCCRP (Organised Crime and Corruption Reporting Project).

        Votre méthode : vous ne vous contentez jamais d'une recherche vide.
        Si le nom du président ne donne rien directement, vous cherchez son épouse,
        ses enfants, ses ministres proches, ses sociétés connues.
        Vous utilisez des sources en anglais ET en français ET en arabe selon le pays.
        
        Vous citez TOUJOURS l'URL complète de chaque source trouvée.
        Vous distinguez clairement ce qui est "documenté" vs "supposé".
        """,
        tools=tools,
        llm=llm,
        verbose=True,
        max_iter=12,
        max_rpm=10,
    )

    # ── AGENT 2 : Cartographe des Réseaux ────────────────────────────────────
    graph_agent = Agent(
        role="Analyste en Cartographie de Réseaux Financiers et Patrimoniaux",
        goal=(
            f"Construire le graphe de connexions entre {dirigeant} et ses actifs "
            f"potentiels à {destination}, basé sur le rapport OSINT collecté."
        ),
        backstory="""
        Expert en analyse de réseaux criminels et financiers, vous avez travaillé
        pour l'UNODC et Transparency International.
        
        Votre spécialité : transformer des informations éparses en une carte claire
        de connexions entre personnes, sociétés et actifs.
        
        Règles que vous respectez toujours :
        - Chaque lien a un poids : 1=documenté avec source, 2=recoupé via presse, 3=supposé
        - Vous n'inventez JAMAIS un nœud sans au moins une mention dans le rapport OSINT
        - Vous incluez TOUJOURS le nœud "dirigeant" comme racine du graphe
        - Le format de sortie est STRICTEMENT un JSON valide
        """,
        tools=[],  # Pas de recherche — raisonnement pur sur le rapport OSINT
        llm=llm,
        verbose=True,
        max_iter=5,
    )

    # ── AGENT 3 : Procureur / Rédacteur ──────────────────────────────────────
    prosecutor_agent = Agent(
        role="Procureur spécialisé en Corruption, Biens Mal Acquis et Transparence Politique",
        goal=(
            f"Rédiger un rapport d'investigation complet sur le voyage de {dirigeant} "
            f"vers {destination}, avec une hypothèse argumentée et un score de risque."
        ),
        backstory="""
        Ancien procureur international, vous avez travaillé pour la Cour Pénale
        Internationale et la CRIET (Bénin). Vous êtes consultant pour le GRECO
        (Groupe d'États contre la Corruption du Conseil de l'Europe).
        
        Votre approche est rigoureusement journalistique et juridique :
        - Vous ne jamais accusez directement — vous exposez des faits et des corrélations
        - Vous distinguez TOUJOURS "documenté" / "recoupé" / "supposé"
        - Vous comparez systématiquement le train de vie constaté avec les revenus officiels
        - Vous mentionnez explicitement les données manquantes et les limites de l'enquête
        - Votre rapport est rédigé de manière à être compréhensible par un journaliste non-expert
        
        Votre rapport inclut OBLIGATOIREMENT :
        1. Un résumé exécutif (3-5 phrases)
        2. L'hypothèse principale sur le but du voyage
        3. L'analyse patrimoniale (revenus officiels vs actifs trouvés)
        4. Le réseau de connexions identifié
        5. Un score de risque de 0 à 10 (10 = corruptibilité maximale évidente)
        6. La liste complète des sources avec leurs URLs
        7. Les limites de l'enquête et les prochaines étapes recommandées
        """,
        tools=[],
        llm=llm,
        verbose=True,
        max_iter=5,
    )

    # ── TÂCHE 1 : Collecte OSINT ──────────────────────────────────────────────
    task_osint = Task(
        description=f"""
        Mène une investigation OSINT complète sur {dirigeant}, chef d'État du {pays}.
        
        CONTEXTE DU VOL SUSPECT :
        - Destination : {destination}
        - Date : {date_vol}
        - Durée du séjour estimée : {duree_sejour}
        - Classification : PERSONNEL (aucun événement officiel trouvé automatiquement)
        {f"- Informations supplémentaires : {context_extra}" if context_extra else ""}
        
        TU DOIS RECHERCHER (dans cet ordre de priorité) :
        
        1. AGENDA OFFICIEL : Y avait-il un sommet, conférence ou visite d'État
           officielle à {destination} autour du {date_vol} ?
           → Si oui, le vol peut être "diplomatique" ou "officiel". Documente-le.
           → Si non, continue l'investigation patrimoniale.
        
        2. RÉSEAU FAMILIAL ET ENTOURAGE :
           → Épouse, enfants, frères/sœurs du dirigeant (noms complets)
           → Ministres proches, directeur de cabinet, chef de la garde présidentielle
           → Hommes d'affaires fréquentant le cercle présidentiel
        
        3. ACTIFS À LA DESTINATION ({destination}) :
           → Biens immobiliers (villas, appartements, hôtels) liés au dirigeant ou à son réseau
           → Sociétés enregistrées localement (OpenCorporates, registre du commerce local)
           → Comptes bancaires (mentions dans la presse)
        
        4. BASES DE DONNÉES OFFSHORE :
           → Panama Papers, Pandora Papers, Paradise Papers (site:offshoreleaks.icij.org)
           → OCCRP Aleph (site:aleph.occrp.org)
           → OpenSanctions (site:opensanctions.org)
        
        5. SANCTIONS ET LISTES PEP :
           → OFAC (Trésor américain), sanctions UE, listes ONU
           → Politically Exposed Persons (PEP) lists
        
        RÈGLE CRITIQUE : Si une recherche retourne peu de résultats, REFORMULE
        avec des synonymes, en anglais, ou en cherchant les membres de la famille.
        Ne passe JAMAIS à la suite avec 0 résultat sans avoir essayé au minimum
        3 formulations différentes.
        
        FORMAT DE SORTIE :
        Rapport structuré en sections, avec TOUTES les URLs sources en format complet.
        """,
        agent=osint_agent,
        expected_output="""
        Rapport OSINT structuré avec :
        - Résultats par catégorie (agenda, famille, actifs, offshore, sanctions)
        - URL complète de chaque source consultée
        - Niveau de fiabilité de chaque information (documenté/recoupé/supposé)
        - Noms de toutes les personnes identifiées dans le réseau
        """,
    )

    # ── TÂCHE 2 : Construction du Graphe ─────────────────────────────────────
    task_graph = Task(
        description=f"""
        À partir du rapport OSINT de l'Agent Traqueur, construis le graphe 
        relationnel JSON de {dirigeant} et de son réseau.
        
        RÈGLES STRICTES :
        
        1. Format JSON OBLIGATOIRE (ne rien écrire avant ou après) :
        {{
          "nodes": [
            {{"id": "dirigeant", "name": "{dirigeant}", "category": "racine", "degree": 0, "details": {{"pays": "{pays}"}}}},
            {{"id": "nom_unique", "name": "Nom Complet", "category": "<type>", "degree": <1-4>, "details": {{...}}}}
          ],
          "edges": [
            {{"source": "id_source", "target": "id_cible", "relation": "type_lien", "weight": <1|2|3>, "source_evidence": "URL ou description", "evidence_type": "<documenté|recoupé|supposé>"}}
          ]
        }}
        
        2. Catégories de nœuds :
           - "racine" (le dirigeant)
           - "famille" (degree 1)
           - "entourage" (degree 2) 
           - "proxy" / "prete_nom" (degree 3)
           - "actif_etranger" / "societe_ecran" / "finance" (degree 4)
        
        3. Poids des liens :
           - 1 = documenté avec URL vérifiable
           - 2 = recoupé via plusieurs sources presse
           - 3 = supposé / mention unique non vérifiée
        
        4. N'invente AUCUN nœud. Seules les entités mentionnées dans le rapport OSINT.
        5. TOUJOURS inclure le nœud "dirigeant" comme point de départ.
        """,
        agent=graph_agent,
        expected_output="JSON valide du graphe relationnel avec nœuds et liens pondérés",
        context=[task_osint],
    )

    # ── TÂCHE 3 : Rapport Final ───────────────────────────────────────────────
    def notify_prosecutor_start(output):
        if status_updater: status_updater("prosecutor", "Préparation du rapport final...")
    task_graph.callback = notify_prosecutor_start

    task_report = Task(
        description=f"""
        Rédige le rapport d'investigation final sur le vol suspect de {dirigeant}
        vers {destination} le {date_vol}.
        
        BASE DE TRAVAIL : Les rapports de l'Agent Traqueur et de l'Agent Cartographe.
        
        STRUCTURE OBLIGATOIRE DU RAPPORT (markdown) :
        
        ## 🔍 RÉSUMÉ EXÉCUTIF
        [3-5 phrases résumant les découvertes clés et l'hypothèse principale]
        
        ## ✈️ CONTEXTE DU VOL
        [Détails du vol, destination, date, durée, classification]
        
        ## 🎯 HYPOTHÈSE PRINCIPALE
        [Quelle est la raison la plus probable de ce voyage ?
         Appuie-toi sur les actifs trouvés, les événements identifiés,
         et le profil du dirigeant. Distingue "hypothèse forte" vs "hypothèse alternative".]
        
        ## 👥 RÉSEAU D'ENTOURAGE IDENTIFIÉ
        [Liste les personnes du réseau avec leurs rôles et liens documentés]
        
        ## 🏛️ ANALYSE PATRIMONIALE
        [Compare les revenus officiels annuels du dirigeant avec les actifs identifiés.
         Utilise des données publiques sur le salaire présidentiel du {pays}.]
        
        ## 🔗 CHAÎNES DE CONNEXION CLÉS
        [Décris les 2-3 connexions les plus significatives trouvées :
         ex: Dirigeant → Fille → Société X → Villa à {destination}]
        
        ## ⚖️ SCORE DE RISQUE : X/10
        [Justifie le score selon : nombre d'actifs trouvés, degré de dissimulation,
         écart revenus/patrimoine, présence dans listes sanctions]
        
        ## 📚 SOURCES CONSULTÉES
        [Liste complète des URLs sources avec date d'accès]
        
        ## ⚠️ LIMITES DE L'ENQUÊTE
        [Ce qui n'a pas pu être vérifié et pourquoi]
        
        ## 📋 PROCHAINES ÉTAPES RECOMMANDÉES
        [Actions concrètes pour approfondir l'enquête]
        
        RÈGLES IMPÉRATIVES :
        ✓ Ne jamais accuser directement — présenter des faits et corrélations
        ✓ Toujours distinguer "documenté" vs "supposé"
        ✓ Citer l'URL de chaque source mentionnée
        ✓ Mentionner explicitement les données manquantes
        """,
        agent=prosecutor_agent,
        expected_output="""
        Rapport markdown complet avec toutes les sections,
        un score de risque justifié (X/10),
        et la liste des sources URL.
        """,
        context=[task_osint, task_graph],
    )

    # ── Lancement du Crew ─────────────────────────────────────────────────────
    try:
        crew = Crew(
            agents=[osint_agent, graph_agent, prosecutor_agent],
            tasks=[task_osint, task_graph, task_report],
            process=Process.sequential,
            verbose=True,
            memory=False, # Désactivé pour éviter l'erreur de quota OpenAI 429
        )

        crew_output = crew.kickoff(inputs={
            "dirigeant": dirigeant,
            "pays": pays,
            "destination": destination,
            "date_vol": date_vol,
            "duree_sejour": duree_sejour,
        })

        # Récupère les sorties de chaque tâche
        osint_raw = task_osint.output.raw if task_osint.output else ""
        graph_raw = task_graph.output.raw if task_graph.output else "{}"
        report_raw = task_report.output.raw if task_report.output else ""

        result.osint_report = osint_raw
        result.graph_json = _extract_graph_json(graph_raw)
        result.final_report = report_raw
        result.sources = _extract_sources_from_report(osint_raw + "\n" + report_raw)
        result.risk_score = _extract_risk_score(report_raw)

    except Exception as e:
        result.error = f"Erreur CrewAI : {str(e)}"
        result.final_report = f"**Erreur lors de l'investigation :** {str(e)}\n\nVérifiez la configuration des clés API (GROQ_API_KEY ou OPENAI_API_KEY)."

    return result


# ── Fallback — si CrewAI n'est pas disponible ────────────────────────────────
def run_investigation_fallback(
    dirigeant: str,
    pays: str,
    destination: str,
    date_vol: str,
) -> InvestigationResult:
    """
    Fallback vers l'ancien pipeline investigator_osint.py si CrewAI n'est pas dispo.
    Conserve la rétrocompatibilité complète.
    """
    result = InvestigationResult()
    
    try:
        import investigator_osint
        osint_data = investigator_osint.gather_all_osint(
            dirigeant=dirigeant,
            pays=pays,
            destination=destination,
            date_vol=date_vol,
        )
        total = osint_data.get("metadata", {}).get("total_results", 0)
        result.osint_report = (
            f"[Fallback OSINT] {total} résultats collectés pour {dirigeant} → {destination}.\n"
            f"Presse: {len(osint_data.get('press', []))} | "
            f"Famille: {len(osint_data.get('family_tree', []))} | "
            f"Actifs: {len(osint_data.get('assets_at_destination', []))} | "
            f"Offshore: {len(osint_data.get('offshore_leaks', []))}"
        )
        result.final_report = (
            f"## Rapport Préliminaire (Mode Dégradé)\n\n"
            f"Investigation sur **{dirigeant}** ({pays}) → **{destination}** le {date_vol}.\n\n"
            f"*CrewAI non disponible. {total} sources collectées via DuckDuckGo.*\n\n"
            f"Installez CrewAI pour une investigation complète : `pip install crewai crewai-tools`"
        )
        result.risk_score = 5
    except Exception as e:
        result.error = str(e)
        result.final_report = f"Erreur fallback : {str(e)}"
    
    return result


# ── Point d'entrée public ─────────────────────────────────────────────────────
def investigate(
    dirigeant: str,
    pays: str,
    destination: str,
    date_vol: str,
    duree_sejour: str = "Inconnue",
    context_extra: str = "",
    status_updater = None,
    model_id: str = "groq/llama-3.3-70b-versatile",
) -> InvestigationResult:
    """
    Point d'entrée principal. Lance CrewAI si disponible, sinon fallback.
    À appeler depuis main.py dans les endpoints /investigate/run/{flight_id}.
    """
    if CREWAI_AVAILABLE and (
        os.getenv("GROQ_API_KEY") or
        os.getenv("OPENAI_API_KEY") or
        os.getenv("ANTHROPIC_API_KEY")
    ):
        return run_investigation_crew(
            dirigeant, pays, destination, date_vol, duree_sejour, context_extra, status_updater, model_id
        )
    else:
        print("[CrewAI] Aucune clé API détectée — basculement sur le mode fallback OSINT.")
        return run_investigation_fallback(dirigeant, pays, destination, date_vol)
