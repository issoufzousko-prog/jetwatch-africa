import { useState, useEffect, useMemo } from 'react';
import { toast } from 'sonner';
import { useCrewAI } from '../hooks/useCrewAI';
import { Activity, RotateCcw, FileText, MapPin, Radio, Search } from 'lucide-react';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import { motion, AnimatePresence } from 'framer-motion';
import AnimatedList from './ui/AnimatedList';
import InvestigationButton from './ui/InvestigationButton';
import InvestigationFlow from './ui/InvestigationFlow';
import Dither from './ui/Dither';
import TextType from './ui/TextType';
import ModelSelector, { type DetectiveModel } from './ui/ModelSelector';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import LogoLoop from './ui/LogoLoop';
import { getFlagUrl, getProfileImageUrl } from '../utils/flags';

interface AiAnalystProps {
  country: string;
  flights: any[];
  leaderName?: string;
}

// Logos for the LogoLoop header (real PNG assets from /public/logos/)
const MODEL_LOGOS = [
  { title: 'HuggingFace',    src: '/logos/huggingface.png', alt: 'HuggingFace' },
  { title: 'Llama — Meta',   src: '/logos/llama.png',       alt: 'Llama' },
  { title: 'Mistral AI',     src: '/logos/mistralai.png',   alt: 'Mistral AI' },
  { title: 'Gemma 2 — Google',src: '/logos/gemma.jpg',      alt: 'Gemma 2' },
  { title: 'Qwen2 — Alibaba',src: '/logos/qwen2.png',       alt: 'Qwen2' },
  { title: 'HuggingFace',    src: '/logos/huggingface.png', alt: 'HuggingFace' },
  { title: 'Llama — Meta',   src: '/logos/llama.png',       alt: 'Llama' },
  { title: 'Mistral AI',     src: '/logos/mistralai.png',   alt: 'Mistral AI' },
  { title: 'Gemma 2 — Google',src: '/logos/gemma.jpg',      alt: 'Gemma 2' },
  { title: 'Qwen2 — Alibaba',src: '/logos/qwen2.png',       alt: 'Qwen2' },
];

type Phase = 'idle' | 'model-select' | 'analysis' | 'report' | 'done';

export default function AiAnalyst({ country, flights, leaderName = 'Inconnu' }: AiAnalystProps) {
  const {
    status: crewStatus,
    result: crewResult,
    error: crewError,
    agents: crewAgents,
    startInvestigation: startCrewInvestigation,
    isInvestigating: isCrewInvestigating,
    reset: resetCrew,
  } = useCrewAI();

  const [phase, setPhase] = useState<Phase>('idle');
  const [selectedFlight, setSelectedFlight] = useState<any | null>(null);
  const [selectedModel, setSelectedModel] = useState<DetectiveModel | null>(null);
  const [report, setReport] = useState<string | null>(null);

  // ── Filtre universel : ne garder que les vols EN VOL ou atterris depuis < 5h ──
  const RETENTION_HOURS = 5;
  const activeFlights = useMemo(() => {
    const nowSec = Math.floor(Date.now() / 1000);
    const retentionSec = RETENTION_HOURS * 3600;
    return flights.filter((f) => {
      // Pas d'arrival_time → encore en vol
      if (!f.arrival_time) return true;
      // Atterri depuis moins de 5h
      return (nowSec - f.arrival_time) < retentionSec;
    });
  }, [flights]);

  // Transition: CrewAI status updates
  useEffect(() => {
    if (crewStatus === 'done' && crewResult) {
      setReport(crewResult.final_report || '');
      setPhase('report');
      toast.success('Investigation CrewAI terminée avec succès');
    } else if (crewStatus === 'error') {
      toast.error('Erreur CrewAI : ' + crewError);
      setReport(crewResult?.final_report || crewError || 'Une erreur est survenue.');
      setPhase('report');
    }
  }, [crewStatus, crewResult, crewError]);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleFlightClick = (flight: any) => {
    setSelectedFlight(flight);
    setReport(null);
    setPhase('model-select');
  };

  const handleModelSelect = (model: DetectiveModel) => {
    setSelectedModel(model);
    setPhase('analysis');
    if (selectedFlight) {
      startCrewInvestigation(selectedFlight.id, model.id);
    }
  };

  const handleReset = () => {
    setPhase('idle');
    setSelectedFlight(null);
    setReport(null);
    resetCrew();
  };

  // ── Flight card component (Premium Tech Look) ─────────────────────────────────────
  const FlightCard = ({ f }: { f: any }) => {
    const pays = f.pays || country;
    const owner = f.dirigeant || leaderName || 'Propriétaire inconnu';
    const isVip = getFlagUrl(pays) === null;
    const imgUrl = getProfileImageUrl(pays, f.photo_url);
    const isFlying = !!f.current_pos;
    const statusColor = isFlying ? '#3b82f6' : '#94a3b8'; 
    const statusLabel = isFlying ? 'EN VOL' : 'AU SOL';

    const handleAction = (e: React.MouseEvent) => {
      e.stopPropagation();
      toast(
        <div className="flex gap-3 items-center">
          <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center shrink-0">
            <Search className="h-5 w-5 text-blue-400" />
          </div>
          <div className="flex flex-col">
            <span className="font-medium text-slate-100">Cible Sélectionnée</span>
            <span className="text-xs text-blue-400/80 font-mono">
              Analyse de {f.tail_number || f.icao24}
            </span>
          </div>
        </div>
      );
      handleFlightClick(f);
    };

    return (
      <div className="group relative flex flex-col sm:flex-row items-center gap-4 w-full bg-slate-900/40 border border-slate-800/50 hover:border-blue-500/30 p-5 rounded-2xl transition-all duration-300 hover:shadow-[0_0_20px_-5px_rgba(59,130,246,0.2)]">
        <div className="relative shrink-0">
          <div className={`overflow-hidden ${isVip
            ? 'w-16 h-16 rounded-2xl border-2 border-slate-700 group-hover:border-blue-500/50 bg-slate-800'
            : 'w-20 h-14 rounded-xl bg-slate-800 border border-slate-700 group-hover:border-blue-500/30'}`}>
            <img
              src={imgUrl}
              alt={pays}
              className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
              onError={(e) => {
                const t = e.target as HTMLImageElement;
                if (t.dataset.failed) return;
                t.dataset.failed = 'true';
                t.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(pays || 'XX')}&background=1e293b&color=fff&rounded=${isVip ? '20' : '8'}`;
              }}
            />
          </div>
          {isFlying && (
            <div className="absolute -top-1 -right-1 w-4 h-4 bg-blue-500 rounded-full border-2 border-slate-900 animate-pulse" />
          )}
        </div>

        <div className="flex-1 min-w-0 text-center sm:text-left">
          <div className="flex items-center justify-center sm:justify-start gap-3 mb-1.5">
            <span className="text-xl font-mono font-black text-white tracking-tighter uppercase">
              {f.tail_number || f.icao24?.toUpperCase() || '——'}
            </span>
            <span
              className="px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-widest flex items-center gap-1.5"
              style={{ backgroundColor: `${statusColor}15`, color: statusColor, border: `1px solid ${statusColor}30` }}
            >
              {statusLabel}
            </span>
          </div>

          <div className="flex flex-col gap-0.5">
            <div className="flex items-center justify-center sm:justify-start gap-2">
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">{pays}</span>
              <span className="w-1 h-1 rounded-full bg-slate-700" />
              <span className="text-xs font-medium text-blue-400/90">{owner}</span>
            </div>
            <div className="flex items-center justify-center sm:justify-start gap-2 text-[11px] font-mono text-slate-500">
              {isFlying ? (
                <><MapPin className="w-3 h-3" /> {f.current_pos[0].toFixed(4)}°, {f.current_pos[1].toFixed(4)}°</>
              ) : (
                <><Radio className="w-3 h-3" /> {f.callsign || 'SIGNAL INACTIF'}</>
              )}
            </div>
          </div>
        </div>

        <div className="shrink-0 w-full sm:w-auto mt-4 sm:mt-0">
          <InvestigationButton 
            variant="solid" 
            onClick={handleAction} 
            className="w-full sm:w-auto px-8 py-3 bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/20 border-t border-white/10"
          >
            Investiguer
          </InvestigationButton>
        </div>
      </div>
    );
  };

  // ── Main Render ────────────────────────────────────────────────────────────

  return (
    <div className="glass-card mb-xl overflow-hidden border-indigo-500/20">
      <div className="bg-black/40 p-md border-b border-glass-border">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-sm">
            <div className="-ml-1 -my-1" style={{ width: 48, height: 48, filter: 'invert(1) hue-rotate(180deg)', mixBlendMode: 'screen', opacity: 0.9 }}>
              <DotLottieReact src="https://lottie.host/88bb8967-f17a-4d63-9c92-e61367b4c975/igdoKeZFk8.lottie" loop autoplay backgroundColor="transparent" />
            </div>
            <div>
              <h3 className="sp-h4 text-foreground">Agent OSINT Autonome</h3>
              <p className="sp-micro text-muted-foreground">CrewAI Task Force — Investigation multi-agents via Groq</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isCrewInvestigating && (
              <div className="flex items-center gap-2 px-2 py-0.5 bg-indigo-500/20 text-indigo-400 rounded border border-indigo-500/30 animate-pulse">
                <Activity className="w-3 h-3" />
                <span className="sp-micro font-mono">INVESTIGATION CREWAI...</span>
              </div>
            )}
            {selectedModel && (
              <div className="sp-micro px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded border border-amber-500/30">
                Modèle: {selectedModel.name}
              </div>
            )}
          </div>
        </div>

        <div className="h-10 flex items-center">
          <LogoLoop logos={MODEL_LOGOS} speed={55} logoHeight={36} gap={56} fadeOut />
        </div>
      </div>

      <div className="p-lg">
        <AnimatePresence mode="wait">
          {phase === 'idle' && (
            <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <div className="flex items-center justify-between mb-4">
                <h4 className="sp-h5 text-foreground">Sélectionner un vol suspect</h4>
                {activeFlights.length > 0 && (
                  <span className="sp-micro px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20 font-mono flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse inline-block" />
                    {activeFlights.length} VOL{activeFlights.length > 1 ? 'S' : ''} ACTIF{activeFlights.length > 1 ? 'S' : ''}
                  </span>
                )}
              </div>

              {activeFlights.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3 text-center">
                  <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center">
                    <Activity className="w-6 h-6 text-slate-500" />
                  </div>
                  <p className="sp-body-semibold text-muted-foreground">Aucun vol actif détecté</p>
                  <p className="sp-micro text-slate-600">Le radar est actif — les vols apparaîtront ici pendant 5h après atterrissage</p>
                </div>
              ) : (
                <AnimatedList
                  items={activeFlights.map((f) => <FlightCard key={f.icao24} f={f} />)}
                  showGradients
                  enableArrowNavigation
                  displayScrollbar
                />
              )}
            </motion.div>
          )}

          {phase === 'model-select' && (
            <motion.div key="model-select" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="py-xl">
              <ModelSelector 
                onSelect={handleModelSelect} 
                onCancel={() => { setPhase('idle'); setSelectedFlight(null); }} 
              />
            </motion.div>
          )}



          {phase === 'analysis' && (
            <motion.div key="analysis" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="w-full h-[400px] relative rounded-xl border border-white/10 overflow-hidden bg-slate-950 flex flex-col items-center justify-center">
              <div className="absolute top-4 left-4 z-10 px-3 py-1 bg-indigo-500/20 text-indigo-400 rounded text-sm font-mono border border-indigo-500/30 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
                DÉTECTIVE IA — {selectedModel?.name || 'Modèle'} EN ANALYSE
              </div>
              <Dither waveColor={[0.8, 0.5, 0.1]} waveAmplitude={0.4} />
              <div className="z-10 text-center px-4 w-full h-full">
                <div className="w-full h-full p-4 flex items-center justify-center">
                  <InvestigationFlow agents={crewAgents} targetName={selectedFlight?.dirigeant || leaderName || 'Cible'} />
                </div>
              </div>
            </motion.div>
          )}

          {(phase === 'report' || phase === 'done') && (
            <motion.div key="report" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="w-full">
              <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
                <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900">
                  <div className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-emerald-400" />
                    <span className="font-mono text-emerald-400 tracking-wider text-sm">RAPPORT D'INVESTIGATION</span>
                    {selectedModel && <span className="sp-micro text-slate-500">— {selectedModel.name}</span>}
                  </div>
                  <InvestigationButton variant="soft" onClick={handleReset}>
                    <RotateCcw className="w-4 h-4 mr-2" />Retour
                  </InvestigationButton>
                </div>
                <div className="p-8 max-w-none text-slate-200">
                  {phase === 'report' ? (
                    <div className="font-mono text-base text-emerald-400">
                      <TextType
                        text={report ? report : 'Génération du rapport...'}
                        typingSpeed={5}
                        showCursor
                        onComplete={() => setPhase('done')}
                      />
                    </div>
                  ) : (
                    <div className="prose prose-invert prose-emerald max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {report && report.trim().length > 10 ? report : '_Aucun rapport valide n\'a pu être généré par le modèle. Le modèle sélectionné est peut-être trop petit pour cette tâche complexe._'}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
