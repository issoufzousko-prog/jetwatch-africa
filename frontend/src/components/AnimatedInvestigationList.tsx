import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BrainCircuit, Search, Building2, Home, FileWarning, Users, Activity, Eye } from 'lucide-react';

interface InvestigationStep {
  thought: string;
  action: string;
  observation: string;
}

interface AnimatedInvestigationListProps {
  steps: InvestigationStep[];
  isInvestigating: boolean;
}

const ACTION_STYLES: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  'SEARCH_PERSON':   { icon: <Search className="w-4 h-4" />,       color: '#1E86FF', label: 'Recherche Personne' },
  'SEARCH_COMPANY':  { icon: <Building2 className="w-4 h-4" />,    color: '#FFB800', label: 'Recherche Société' },
  'SEARCH_PROPERTY': { icon: <Home className="w-4 h-4" />,         color: '#00C9A7', label: 'Recherche Bien Immobilier' },
  'SEARCH_ALEPH':    { icon: <FileWarning className="w-4 h-4" />,  color: '#FF3D71', label: 'Panama Papers / OCCRP' },
  'SEARCH_FAMILY':   { icon: <Users className="w-4 h-4" />,        color: '#FF69B4', label: 'Arbre Généalogique' },
  'SEARCH_SALARY':   { icon: <Activity className="w-4 h-4" />,     color: '#A855F7', label: 'Revenus Déclarés' },
  'PATHFIND':        { icon: <Eye className="w-4 h-4" />,          color: '#F97316', label: 'Traçage de Connexion' },
  'SEARCH_SATELLITE':{ icon: <Eye className="w-4 h-4" />,          color: '#06B6D4', label: 'Vue Satellite' },
  'FETCH_IMAGE':     { icon: <Eye className="w-4 h-4" />,          color: '#8B5CF6', label: 'Capture Visuelle' },
};

function getActionMeta(action: string) {
  for (const key of Object.keys(ACTION_STYLES)) {
    if (action.includes(key)) return ACTION_STYLES[key];
  }
  return { icon: <BrainCircuit className="w-4 h-4" />, color: '#6366F1', label: 'Raisonnement' };
}

function timeAgo(index: number, total: number): string {
  const seconds = (total - index) * 8;
  if (seconds < 60) return `il y a ${seconds}s`;
  return `il y a ${Math.floor(seconds / 60)}min`;
}

export default function AnimatedInvestigationList({ steps, isInvestigating }: AnimatedInvestigationListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [steps]);

  return (
    <div className="relative flex flex-col h-full overflow-hidden">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
        <AnimatePresence initial={false}>
          {steps.map((step, idx) => {
            const meta = getActionMeta(step.action);
            return (
              <motion.figure
                key={idx}
                initial={{ opacity: 0, y: 40, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ type: 'spring', stiffness: 300, damping: 30, delay: 0.05 }}
                className="relative w-full cursor-pointer overflow-hidden rounded-2xl p-4
                  transition-all duration-200 ease-in-out hover:scale-[1.02]
                  bg-transparent backdrop-blur-md border border-white/10
                  shadow-[0_-20px_80px_-20px_#ffffff1f_inset]"
              >
                <div className="flex flex-row items-start gap-3">
                  {/* Icône de l'action */}
                  <div
                    className="flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-xl"
                    style={{ backgroundColor: meta.color + '20', color: meta.color }}
                  >
                    {meta.icon}
                  </div>

                  {/* Contenu */}
                  <div className="flex flex-col overflow-hidden flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-white truncate">{meta.label}</span>
                      <span className="text-xs text-slate-500">·</span>
                      <span className="text-xs text-slate-500 flex-shrink-0">{timeAgo(idx, steps.length)}</span>
                    </div>
                    
                    {/* Thought */}
                    <p className="text-xs text-white/60 mt-1 line-clamp-2 leading-relaxed">
                      {step.thought}
                    </p>

                    {/* Action détail */}
                    <p className="text-xs font-mono mt-1.5 truncate" style={{ color: meta.color }}>
                      {step.action}
                    </p>

                    {/* Observation (collapsible) */}
                    {step.observation && (
                      <div className="mt-2 p-2 rounded-lg bg-black/30 border border-white/5 max-h-20 overflow-y-auto custom-scrollbar">
                        <p className="text-[10px] text-slate-500 font-mono whitespace-pre-wrap leading-relaxed">
                          {step.observation.substring(0, 300)}{step.observation.length > 300 ? '...' : ''}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </motion.figure>
            );
          })}
        </AnimatePresence>

        {/* Indicateur de chargement */}
        {isInvestigating && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3 p-3 rounded-xl bg-blue-500/5 border border-blue-500/20"
          >
            <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-blue-400 font-medium">Convergence des algorithmes...</span>
          </motion.div>
        )}
      </div>

      {/* Gradient de fondu en bas */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-black/90 to-transparent z-10" />
    </div>
  );
}
