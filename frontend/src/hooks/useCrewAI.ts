import { useState, useCallback, useRef } from 'react';
import { api } from '../services/api';

export type CrewAIStatus = 'not_started' | 'pending' | 'running' | 'done' | 'error';

export type AgentPhase =
  | 'idle'
  | 'searching'
  | 'mapping'
  | 'analyzing'
  | 'done'
  | 'error';

export interface AgentLog {
  timestamp: string;
  message: string;
}

export interface AgentState {
  id: 'osint' | 'cartographer' | 'prosecutor';
  name: string;
  phase: AgentPhase;
  logs: AgentLog[];
  score?: number;
  sources?: string[];
}

export interface CrewAIResult {
  status: CrewAIStatus;
  flight_id: number;
  final_report?: string;
  graph_json?: any;
  risk_score?: number;
  sources?: string[];
  error?: string;
  agents?: AgentState[];
}

// Sequence of agent activations simulated for UX while backend runs
const AGENT_SEQUENCE: Array<{
  ms: number;
  agentId: AgentState['id'];
  phase: AgentPhase;
  log: string;
}> = [
  { ms: 0,    agentId: 'osint',        phase: 'searching', log: 'Initialisation du Traqueur OSINT...' },
  { ms: 500,  agentId: 'cartographer', phase: 'mapping',   log: 'Préparation du canevas relationnel...' },
  { ms: 1000, agentId: 'prosecutor',   phase: 'analyzing', log: 'Chargement des lois anti-corruption...' },
  { ms: 3000, agentId: 'osint',        phase: 'searching', log: 'Requêtes Serper.dev sur la cible...' },
  { ms: 5000, agentId: 'cartographer', phase: 'mapping',   log: 'Écoute des signaux ADS-B...' },
  { ms: 8000, agentId: 'osint',        phase: 'searching', log: 'Analyse des fuites Offshore Leaks...' },
  { ms: 11000,agentId: 'prosecutor',   phase: 'analyzing', log: 'Vérification du profil PEP...' },
  { ms: 14000,agentId: 'cartographer', phase: 'mapping',   log: 'Construction du graphe de connaissance...' },
  { ms: 18000,agentId: 'osint',        phase: 'searching', log: 'Croisement avec les données bancaires...' },
  { ms: 22000,agentId: 'prosecutor',   phase: 'analyzing', log: 'Calcul des infractions potentielles...' },
  { ms: 26000,agentId: 'cartographer', phase: 'mapping',   log: 'Finalisation des nœuds suspects...' },
  { ms: 29000,agentId: 'prosecutor',   phase: 'analyzing', log: 'Génération du réquisitoire final...' },
];

const INITIAL_AGENTS: AgentState[] = [
  { id: 'osint',        name: 'Traqueur OSINT',      phase: 'idle', logs: [], sources: [] },
  { id: 'cartographer', name: 'Cartographe',          phase: 'idle', logs: [] },
  { id: 'prosecutor',   name: 'Procureur Analytique', phase: 'idle', logs: [] },
];

export function useCrewAI() {
  const [status, setStatus] = useState<CrewAIStatus>('not_started');
  const [result, setResult] = useState<CrewAIResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentState[]>(INITIAL_AGENTS);

  const pollingInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const sequenceTimers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const addAgentLog = useCallback((agentId: AgentState['id'], message: string) => {
    setAgents(prev => prev.map(a =>
      a.id === agentId
        ? { ...a, logs: [...a.logs, { timestamp: new Date().toLocaleTimeString('fr-FR'), message }] }
        : a
    ));
  }, []);

  const setAgentPhase = useCallback((agentId: AgentState['id'], phase: AgentPhase) => {
    setAgents(prev => prev.map(a => a.id === agentId ? { ...a, phase } : a));
  }, []);

  const stopPolling = useCallback(() => {
    if (pollingInterval.current) { clearInterval(pollingInterval.current); pollingInterval.current = null; }
    sequenceTimers.current.forEach(t => clearTimeout(t));
    sequenceTimers.current = [];
  }, []);

  const startSequenceAnimation = useCallback(() => {
    AGENT_SEQUENCE.forEach(({ ms, agentId, phase, log }) => {
      const t = setTimeout(() => {
        setAgentPhase(agentId, phase);
        addAgentLog(agentId, log);
      }, ms);
      sequenceTimers.current.push(t);
    });
  }, [setAgentPhase, addAgentLog]);

  const pollStatus = useCallback(async (flightId: number) => {
    try {
      const data = await api.getCrewAIStatus(flightId);
      setStatus(data.status);
      if (data.status === 'done' || data.status === 'error') {
        const finalResult: CrewAIResult = { ...data, agents };
        setResult(finalResult);
        stopPolling();
        if (data.status === 'done') {
          setAgents(prev => prev.map(a => ({ ...a, phase: 'done' })));
          if (data.risk_score !== undefined) {
            setAgents(prev => prev.map(a =>
              a.id === 'prosecutor' ? { ...a, score: data.risk_score } : a
            ));
          }
        } else {
          setError(data.error || 'Une erreur est survenue.');
          setAgents(prev => prev.map(a => ({ ...a, phase: 'error' })));
        }
      }
    } catch (err: any) {
      console.error('[CrewAI Hook] Polling error:', err);
    }
  }, [stopPolling, agents]);

  const startInvestigation = useCallback(async (flightId: number, modelId: string) => {
    try {
      setStatus('pending');
      setError(null);
      setResult(null);
      setAgents(INITIAL_AGENTS);

      startSequenceAnimation();

      const data = await api.runCrewAI(flightId, modelId);
      setStatus(data.status);

      stopPolling();
      pollingInterval.current = setInterval(() => pollStatus(flightId), 3000);
    } catch (err: any) {
      setStatus('error');
      setError(err.message || 'Impossible de lancer l\'investigation CrewAI.');
      setAgents(prev => prev.map(a => ({ ...a, phase: 'error' })));
    }
  }, [pollStatus, stopPolling, startSequenceAnimation]);

  const reset = useCallback(() => {
    stopPolling();
    setStatus('not_started');
    setResult(null);
    setError(null);
    setAgents(INITIAL_AGENTS);
  }, [stopPolling]);

  return {
    status,
    result,
    error,
    agents,
    startInvestigation,
    reset,
    isInvestigating: status === 'pending' || status === 'running',
  };
}
