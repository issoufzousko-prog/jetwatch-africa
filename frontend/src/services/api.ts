/**
 * JetWatch Africa — Service API sécurisé
 *
 * Chaque requête vers le backend est automatiquement protégée par :
 *  1. EC Proof-of-Work : résolution d'un challenge mathématique (anti-bot)
 *  2. ECDH Session ID : identification de la session chiffrée
 *  3. JWT Bearer token : authentification utilisateur
 *  4. API Key : clé statique de service
 */

import { getPoWToken, getSessionId, initEcdhSession } from '../lib/jetwatch-crypto';

export const API_URL = import.meta.env.VITE_API_URL || '';
const API_KEY = 'jetwatch-local-secure-key-2026';

// ── Headers de base (auth) ────────────────────────────────────────────

const getAuthHeaders = (): Record<string, string> => {
  const headers: Record<string, string> = {};
  const token = localStorage.getItem('auth_token');
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
};

// ── Headers sécurisés avec PoW ────────────────────────────────────────

/**
 * Construit les headers incluant le token PoW résolu.
 * Le Web Worker résout le challenge en ~65ms en arrière-plan.
 */
async function getSecureHeaders(withBody = false): Promise<Record<string, string>> {
  // Obtenir un token PoW frais (à usage unique)
  const { challengeId, nonce } = await getPoWToken();

  const headers: Record<string, string> = {
    'X-Jetwatch-Api-Key': API_KEY,
    'X-PoW-Challenge-Id': challengeId,
    'X-PoW-Nonce': nonce,
  };

  // Ajouter le session ID ECDH si disponible
  const sessionId = getSessionId();
  if (sessionId) headers['X-Session-Id'] = sessionId;

  // Ajouter auth JWT si connecté
  const token = localStorage.getItem('auth_token');
  if (token) headers['Authorization'] = `Bearer ${token}`;

  if (withBody) headers['Content-Type'] = 'application/json';

  return headers;
}

// ── Requête sécurisée générique ───────────────────────────────────────

async function secureRequest(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const isBody = ['POST', 'PUT', 'PATCH'].includes((options.method || 'GET').toUpperCase());
  const headers = await getSecureHeaders(isBody);
  return fetch(url, { ...options, headers: { ...headers, ...(options.headers || {}) } });
}

// ── API publique ──────────────────────────────────────────────────────

export const api = {

  // ── Vols & Score ────────────────────────────────────────────────────

  getFlights: async (pays: string) => {
    const resp = await secureRequest(`${API_URL}/vols/${encodeURIComponent(pays)}`);
    if (!resp.ok) {
      if (resp.status === 404) return [];
      throw new Error('Failed to fetch flights');
    }
    return resp.json();
  },

  getScore: async (pays: string) => {
    const resp = await secureRequest(`${API_URL}/score/${encodeURIComponent(pays)}`);
    if (!resp.ok) {
      if (resp.status === 404) return {
        pays, dirigeant: 'Inconnu', niveau: 'NORMAL',
        score_global: 0, total_vols: 0, total_heures: 0,
        co2_kg: 0, cout_usd: 0, ratio_suspects: 0, taux_ads_b: 0
      };
      throw new Error('Failed to fetch score');
    }
    return resp.json();
  },

  getClassement: async () => {
    const resp = await secureRequest(`${API_URL}/classement`);
    if (!resp.ok) throw new Error('Failed to fetch classement');
    return resp.json();
  },

  // ── Live tracking ────────────────────────────────────────────────────

  getLiveTrajectories: async () => {
    const resp = await secureRequest(`${API_URL}/live/trajectories`);
    if (!resp.ok) throw new Error('Failed to fetch trajectories');
    return resp.json();
  },

  getPredictions: async (icao24: string) => {
    const resp = await secureRequest(`${API_URL}/live/predictions/${encodeURIComponent(icao24)}`);
    if (!resp.ok) throw new Error('Failed to fetch predictions');
    return resp.json();
  },

  // ── Pays (public — sans PoW pour la page d'accueil) ─────────────────

  getCountries: async () => {
    // Route publique, encore protégée par PoW mais sans auth
    const resp = await secureRequest(`${API_URL}/pays`);
    if (!resp.ok) throw new Error('Failed to fetch countries');
    return resp.json();
  },

  // ── OSINT ────────────────────────────────────────────────────────────

  osintLookup: async (tailNumber: string) => {
    const resp = await secureRequest(`${API_URL}/osint/lookup/${encodeURIComponent(tailNumber)}`);
    if (!resp.ok) {
      if (resp.status === 404) throw new Error('Aéronef introuvable dans la base publique');
      throw new Error('Erreur de scan OSINT');
    }
    return resp.json();
  },

  osintDiscover: async (pays: string) => {
    const resp = await secureRequest(`${API_URL}/osint/discover/${encodeURIComponent(pays)}`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail || 'Erreur lors de la découverte OSINT');
    }
    return resp.json();
  },

  // ── Flotte ───────────────────────────────────────────────────────────

  addJetToFleet: async (data: { pays: string; icao24: string; tail_number: string; description: string }) => {
    const resp = await secureRequest(`${API_URL}/flotte/ajouter`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail || 'Erreur lors de l\'ajout à la flotte');
    }
    return resp.json();
  },

  getFleet: async (pays: string) => {
    const resp = await secureRequest(`${API_URL}/flotte/${encodeURIComponent(pays)}`);
    if (!resp.ok) {
      let errText = `HTTP ${resp.status}`;
      try {
        const errJson = await resp.json();
        errText = errJson.detail || errJson.message || errText;
      } catch (e) {
        errText = await resp.text().catch(() => errText);
      }
      throw new Error(`Erreur récupération flotte: ${errText}`);
    }
    return resp.json();
  },

  // ── VIP ──────────────────────────────────────────────────────────────

  addVIP: async (nom: string) => {
    const resp = await secureRequest(`${API_URL}/vip/ajouter`, {
      method: 'POST',
      body: JSON.stringify({ nom }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail || 'Erreur lors de la création du VIP');
    }
    return resp.json();
  },

  // ── CrewAI (Autonomous Multi-Agent Investigation) ────────────────────

  /**
   * Lance une investigation CrewAI autonome en arrière-plan.
   * Retourne un objet contenant le statut 'pending' et l'URL de polling.
   */
  runCrewAI: async (flightId: number, modelId: string) => {
    const resp = await secureRequest(`${API_URL}/investigate/run/${flightId}`, {
      method: 'POST',
      body: JSON.stringify({ model_id: modelId }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail || 'Erreur lors du lancement de CrewAI');
    }
    return resp.json();
  },

  /**
   * Récupère le statut actuel d'une investigation CrewAI.
   * Statuts: pending | running | done | error
   */
  getCrewAIStatus: async (flightId: number) => {
    const resp = await secureRequest(`${API_URL}/investigate/status/${flightId}`);
    if (!resp.ok) throw new Error('Impossible de récupérer le statut de l\'investigation');
    return resp.json();
  },

  // ── Investigation (WebGPU Legacy) ──────────────────────────────────────

  getInvestigationReport: async (flightId: number) => {
    const resp = await secureRequest(`${API_URL}/investigation/${flightId}`);
    if (!resp.ok) throw new Error('Rapport d\'investigation indisponible');
    return resp.json();
  },

  getInvestigationGraph: async (flightId: number) => {
    const resp = await secureRequest(`${API_URL}/investigation/${flightId}/graph`);
    if (!resp.ok) throw new Error('Graphe d\'investigation indisponible');
    return resp.json();
  },

  /**
   * Couche 3+4 — Déclenche OSINT + Dijkstra (Python pur, sans LLM).
   * Retourne les données brutes + les prompts pré-construits pour WebLLM.
   */
  prepareInvestigation: async (flightId: number) => {
    const resp = await secureRequest(`${API_URL}/investigate/prepare/${flightId}`, { method: 'POST' });
    if (!resp.ok) throw new Error('Erreur lors de la préparation de l\'investigation');
    return resp.json();
  },

  /**
   * Couche 5 — Soumet le rapport généré par WebLLM pour stockage en base.
   */
  submitInvestigationReport: async (
    flightId: number,
    report: { investigation_report: string; knowledge_graph: string; risk_score: number }
  ) => {
    const resp = await secureRequest(`${API_URL}/investigate/report/${flightId}`, {
      method: 'POST',
      body: JSON.stringify(report),
    });
    if (!resp.ok) throw new Error('Erreur lors de la sauvegarde du rapport');
    return resp.json();
  },

  // ── Classification WebGPU ───────────────────────────────────────────────

  /**
   * Couche 2 — Étape 1/2 : récupère les vols non-classifiés + prompts LLM.
   * Le frontend soumettra chaque prompt à WebLLM (WebGPU).
   */
  getPendingFlights: async (pays: string) => {
    const resp = await secureRequest(`${API_URL}/classify/pending/${encodeURIComponent(pays)}`);
    if (!resp.ok) throw new Error('Erreur lors de la récupération des vols en attente');
    return resp.json();
  },

  /**
   * Couche 2 — Étape 2/2 : soumet la classification WebLLM au backend.
   * Retourne { needs_investigation: boolean }.
   */
  submitClassificationResult: async (result: {
    flight_id: number;
    classification: string;
    confiance?: string;
    evenement_confirme?: string;
    sources_consultees?: string[];
    signal_alerte?: string;
    motif_alerte?: string;
    raw_response?: string;
  }) => {
    const resp = await secureRequest(`${API_URL}/classify/result`, {
      method: 'POST',
      body: JSON.stringify(result),
    });
    if (!resp.ok) throw new Error('Erreur lors de la soumission de la classification');
    return resp.json();
  },

  /**
   * @deprecated Utiliser runBatchClassification() du hook useWebLLM à la place.
   * Conservé pour compatibilité — le backend retourne désormais les instructions WebGPU.
   */
  classifyFlights: async (pays: string) => {
    const resp = await secureRequest(`${API_URL}/classify/${encodeURIComponent(pays)}`, { method: 'POST' });
    if (!resp.ok) throw new Error('Erreur lors de la classification');
    return resp.json();
  },

  // ── Monitoring ────────────────────────────────────────────────────────

  getPowStats: async () => {
    const resp = await secureRequest(`${API_URL}/pow/stats`);
    if (!resp.ok) throw new Error('Impossible de lire les stats PoW');
    return resp.json();
  },

  // ── Auth ──────────────────────────────────────────────────────────────

  getCurrentUser: async () => {
    const resp = await secureRequest(`${API_URL}/api/users/me`);
    if (!resp.ok) throw new Error('Invalid token');
    return resp.json();
  },

  getUsersCount: async () => {
    const resp = await secureRequest(`${API_URL}/api/users/count`);
    if (!resp.ok) throw new Error('Failed to fetch users count');
    return resp.json();
  },
};

// ── Initialisation au démarrage ───────────────────────────────────────

/**
 * À appeler une seule fois au montage de l'application (dans App.tsx).
 * Lance le handshake ECDH et pré-résout le premier challenge PoW.
 */
export async function initSecurity(): Promise<void> {
  // 1. Handshake ECDH pour établir la clé de session
  await initEcdhSession();
  // 2. Pré-résoudre un premier challenge PoW en avance (invisible pour l'utilisateur)
  getPoWToken().catch(() => {/* Echec silencieux — sera retentée à la prochaine requête */});
}
