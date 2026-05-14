import { useState, useCallback } from 'react';
import { CreateMLCEngine, MLCEngine } from '@mlc-ai/web-llm';
import type { InitProgressReport } from '@mlc-ai/web-llm';
import { API_URL } from '../services/api';

// ─── Interfaces ──────────────────────────────────────────────────────────────

interface GraphData {
  nodes: any[];
  links: any[];
  stats?: any;
}

interface InvestigationStep {
  thought: string;
  action: string;
  observation: string;
}

export interface ReportSection {
  title: string;
  text: string;
  imageUrl?: string;
  satelliteUrl?: string;
  sourceQuote?: string;
  sourceName?: string;
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useWebLLM() {
  const [engine, setEngine] = useState<MLCEngine | null>(null);
  const [loadedModelId, setLoadedModelId] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Investigation states
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [investigationSteps, setInvestigationSteps] = useState<InvestigationStep[]>([]);
  const [evidenceImages, setEvidenceImages] = useState<string[]>([]);
  const [reportSections, setReportSections] = useState<ReportSection[]>([]);

  // ── Model initialization (modèle choisi par l'utilisateur) ──────────────

  const initModel = useCallback(async (modelId: string) => {
    // Already loaded with same model — do nothing
    if (engine && loadedModelId === modelId) return;

    // If a different model is loaded, reset engine
    if (engine) {
      try { await engine.unload(); } catch {}
    }

    try {
      setIsInitializing(true);
      setProgress(0);
      setError(null);

      const initProgressCallback = (report: InitProgressReport) => {
        const match = report.text.match(/(\d+)%\s+completed/);
        if (match && match[1]) {
          setProgress(parseInt(match[1], 10));
        } else if (report.progress !== undefined && report.progress !== null) {
          setProgress(Math.round(report.progress * 100));
        }
        setStatusText(report.text);
      };

      const newEngine = await CreateMLCEngine(modelId, {
        initProgressCallback,
      });

      setEngine(newEngine);
      setLoadedModelId(modelId);
    } catch (err: any) {
      console.error('WebLLM Init Error:', err);
      setError(err.message || 'Impossible de charger le modèle.');
      setEngine(null);
      setLoadedModelId(null);
    } finally {
      setIsInitializing(false);
    }
  }, [engine, loadedModelId]);

  // ── Agent 1 — OSINT via Command R+ (backend Cohere) ─────────────────────
  // Le backend Python appelle l'API Cohere avec command-r-plus et effectue
  // les recherches dans les bases publiques (Aleph, OCCRP, presse, etc.)

  const runOsintAgent = async (
    targetName: string,
    targetCountry: string,
    targetCity: string,
    sessionId: string,
    onGraphUpdate: (data: GraphData) => void,
    onStepUpdate: (step: InvestigationStep) => void,
  ): Promise<string> => {
    const token = localStorage.getItem('auth_token');
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    };

    const powChallengeId = sessionStorage.getItem('pow_challenge_id');
    const powNonce = sessionStorage.getItem('pow_nonce');
    if (powChallengeId && powNonce) {
      headers['X-PoW-Challenge-Id'] = powChallengeId;
      headers['X-PoW-Nonce'] = powNonce;
    }

    try {
      const res = await fetch(`${API_URL}/api/osint/run`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          target_name: targetName,
          target_country: targetCountry,
          target_city: targetCity,
          session_id: sessionId,
        }),
      });

      if (!res.ok) {
        // Fallback: return empty but structured results so detective can still run
        console.warn('[OSINT Agent] Backend unavailable, using minimal context');
        return JSON.stringify({
          target: targetName,
          country: targetCountry,
          destination: targetCity,
          findings: [],
          note: 'Données OSINT limitées — backend Cohere non disponible.',
        });
      }

      const data = await res.json();

      // Update graph if backend returns graph data
      if (data.graph) onGraphUpdate(data.graph);

      // Emit steps for the UI
      if (data.steps) {
        for (const step of data.steps) {
          onStepUpdate(step);
        }
      }

      return JSON.stringify(data.summary || data);
    } catch (e: any) {
      console.warn('[OSINT Agent] Error:', e.message);
      return JSON.stringify({ target: targetName, country: targetCountry, destination: targetCity, findings: [] });
    }
  };

  // ── Agent 2 — Detective Analysis (WebLLM, modèle choisi par user) ────────

  const startInvestigation = async (
    targetName: string,
    targetCountry: string,
    targetCity: string,
    exactDeparture: number[] | null,
    exactArrival: number[] | null,
    sessionId: string,
    onGraphUpdate: (data: GraphData) => void,
    onReportUpdate: (report: string) => void,
    onStepUpdate?: (step: InvestigationStep) => void,
  ) => {
    if (!engine) throw new Error("Le moteur IA n'est pas prêt.");

    setIsInvestigating(true);
    setInvestigationSteps([]);
    setEvidenceImages([]);
    setReportSections([]);

    try {
      // ── Phase 1 : OSINT Agent (Command R+ via backend) ──────────────────
      const osintSummary = await runOsintAgent(
        targetName,
        targetCountry,
        targetCity,
        sessionId,
        onGraphUpdate,
        (step) => {
          setInvestigationSteps(prev => [...prev, step]);
          if (onStepUpdate) onStepUpdate(step);
        },
      );

      // ── Phase 2 : Detective Agent (WebLLM local) ─────────────────────────
      const detectiveSystemPrompt = `Tu es un détective privé de haut niveau, spécialisé dans l'investigation des biens mal acquis et la transparence politique en Afrique.

Ta mission : Analyser les données OSINT collectées sur ${targetName} (${targetCountry}) et rédiger un rapport d'investigation complet et structuré.

Données OSINT disponibles :
${osintSummary}

Informations de vol :
- Cible : ${targetName} — ${targetCountry}
- Destination suspecte : ${targetCity}
- Départ GPS : ${exactDeparture ? exactDeparture.join(', ') : 'Inconnu'}
- Arrivée GPS : ${exactArrival ? exactArrival.join(', ') : 'Inconnue'}

Méthode d'analyse : Prédiction → Contexte politique → Patrimoine vs revenus → Liens familiaux → Conclusion

Format OBLIGATOIRE du rapport (markdown) :

## Contexte & Prédiction du voyage
[Analyse de la raison probable du déplacement]

## Profil Politique & Historique
[Contexte politique de la cible]

## Analyse Patrimoniale
[Biens déclarés vs revenus légaux]

## Connexions & Réseaux
[Liens familiaux, business, offshore]

## Conclusion & Score de Risque
Score de transparence : X/10
[Verdict final]`;

      const reply = await engine.chat.completions.create({
        messages: [
          { role: 'system', content: detectiveSystemPrompt },
          { role: 'user', content: 'Génère le rapport d\'investigation complet.' },
        ],
        temperature: 0.2,
        max_tokens: 2000,
      });

      const finalReport = reply.choices[0].message.content || '';

      // Parse sections
      const sections: ReportSection[] = [];
      const parts = finalReport.split('##').filter(p => p.trim());
      for (const part of parts) {
        const lines = part.trim().split('\n');
        const title = lines[0].trim();
        const text = lines.slice(1).join('\n').trim();
        if (title && text) {
          sections.push({ title, text });
        }
      }
      if (sections.length === 0) {
        sections.push({ title: "Rapport d'Investigation", text: finalReport });
      }

      setReportSections(sections);
      onReportUpdate(finalReport);

    } catch (err: any) {
      console.error('Investigation Error:', err);
      setError("Erreur lors de l'investigation : " + err.message);
    } finally {
      setIsInvestigating(false);
    }
  };

  // ── Batch classification (WebGPU, pipeline couches 2→5) ──────────────────

  const [isClassifying, setIsClassifying] = useState(false);
  const [classificationProgress, setClassificationProgress] = useState<{
    current: number;
    total: number;
    currentFlight: string;
    phase: string;
  } | null>(null);

  const runBatchClassification = async (
    pays: string,
    authToken: string,
    onProgress?: (current: number, total: number, phase: string, flight: string) => void
  ): Promise<{ classified: number; investigated: number; errors: number }> => {
    if (!engine) throw new Error("Le moteur WebLLM n'est pas initialisé.");

    setIsClassifying(true);
    setClassificationProgress(null);

    const headers: Record<string, string> = {
      'Authorization': `Bearer ${authToken}`,
      'Content-Type': 'application/json',
    };

    const powChallengeId = sessionStorage.getItem('pow_challenge_id');
    const powNonce = sessionStorage.getItem('pow_nonce');
    if (powChallengeId && powNonce) {
      headers['X-PoW-Challenge-Id'] = powChallengeId;
      headers['X-PoW-Nonce'] = powNonce;
    }

    let classified = 0;
    let investigated = 0;
    let errors = 0;

    try {
      const pendingRes = await fetch(
        `${API_URL}/classify/pending/${encodeURIComponent(pays)}`,
        { headers }
      );
      if (!pendingRes.ok) throw new Error(`Erreur GET /classify/pending: ${pendingRes.status}`);

      const { vols, total } = await pendingRes.json();
      if (!vols || vols.length === 0) {
        return { classified: 0, investigated: 0, errors: 0 };
      }

      for (let i = 0; i < vols.length; i++) {
        const vol = vols[i];
        const flightLabel = `${vol.departure_airport || '?'} → ${vol.arrival_airport || '?'}`;

        try {
          setClassificationProgress({ current: i + 1, total, currentFlight: flightLabel, phase: 'classification' });
          onProgress?.(i + 1, total, 'classification', flightLabel);

          const classifReply = await engine.chat.completions.create({
            messages: [
              { role: 'system', content: 'Tu es un analyste expert en transparence politique africaine.' },
              { role: 'user', content: vol.prompt },
            ],
            temperature: 0.1,
            max_tokens: 400,
          });

          const rawClassif = classifReply.choices[0].message.content || '';
          let classifData: Record<string, any> = {};
          const jsonStart = rawClassif.indexOf('{');
          const jsonEnd = rawClassif.lastIndexOf('}');
          if (jsonStart !== -1 && jsonEnd > jsonStart) {
            try { classifData = JSON.parse(rawClassif.slice(jsonStart, jsonEnd + 1)); } catch {}
          }

          if (!classifData.classification) {
            const lower = rawClassif.toLowerCase();
            classifData.classification = lower.includes('diplomatique')
              ? 'diplomatique' : lower.includes('personnel')
              ? 'personnel' : 'officiel';
            classifData.confiance = 'faible';
          }

          const resultRes = await fetch(`${API_URL}/classify/result`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
              flight_id: vol.id,
              classification: classifData.classification,
              confiance: classifData.confiance ?? 'faible',
              evenement_confirme: classifData.evenement_confirme ?? 'aucun',
              sources_consultees: classifData.sources_consultees ?? [],
              signal_alerte: classifData.signal_alerte ?? 'non',
              motif_alerte: classifData.motif_alerte ?? '',
              raw_response: rawClassif.slice(0, 500),
            }),
          });
          if (!resultRes.ok) throw new Error(`Erreur POST /classify/result: ${resultRes.status}`);
          classified++;
        } catch (volErr: any) {
          errors++;
          console.error(`[WebGPU] Erreur vol ${vol.id}:`, volErr.message);
        }
      }

      return { classified, investigated, errors };
    } catch (err: any) {
      console.error('[WebGPU] Erreur pipeline batch:', err);
      setError('Erreur pipeline : ' + err.message);
      return { classified, investigated, errors: errors + 1 };
    } finally {
      setIsClassifying(false);
      setClassificationProgress(null);
    }
  };

  return {
    engine,
    loadedModelId,
    isInitializing,
    progress,
    statusText,
    error,
    isInvestigating,
    investigationSteps,
    evidenceImages,
    reportSections,
    isClassifying,
    classificationProgress,
    runBatchClassification,
    initModel,
    startInvestigation,
  };
}
