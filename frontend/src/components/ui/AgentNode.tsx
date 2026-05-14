import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { Activity, Search, ShieldCheck, Cpu, CheckCircle2, AlertTriangle, Loader2, Plane, Radar, Network, Scale } from 'lucide-react';
import { type AgentState } from '../../hooks/useCrewAI';
import { motion, AnimatePresence } from 'framer-motion';

const getIcon = (id: string, className: string) => {
  switch (id) {
    case 'osint': return <Radar className={className} />;
    case 'cartographer': return <Network className={className} />;
    case 'prosecutor': return <Scale className={className} />;
    default: return <Activity className={className} />;
  }
};

const getStatusColor = (phase: AgentState['phase']) => {
  switch (phase) {
    case 'idle': return 'border-slate-800 bg-slate-900/50 text-slate-500';
    case 'searching':
    case 'mapping':
    case 'analyzing': return 'border-amber-500/50 bg-amber-500/10 text-amber-400';
    case 'done': return 'border-emerald-500/50 bg-emerald-500/10 text-emerald-400';
    case 'error': return 'border-red-500/50 bg-red-500/10 text-red-400';
    default: return 'border-slate-800 bg-slate-900/50 text-slate-500';
  }
};

const getStatusLabel = (phase: AgentState['phase']) => {
  switch (phase) {
    case 'idle': return 'EN ATTENTE';
    case 'searching': return 'RECHERCHE OSINT';
    case 'mapping': return 'CARTOGRAPHIE';
    case 'analyzing': return 'ANALYSE';
    case 'done': return 'TERMINÉ';
    case 'error': return 'ERREUR';
    default: return 'INCONNU';
  }
};

export default function AgentNode({ data }: { data: AgentState & { isTarget?: boolean, targetName?: string, isStart?: boolean } }) {
  
  if (data.isTarget) {
    return (
      <div className="px-4 py-2 bg-slate-900 border border-indigo-500/50 rounded-xl shadow-[0_0_15px_-3px_rgba(99,102,241,0.3)]">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center">
            <img src="/icons/Cible d'Investigation.svg" className="w-5 h-5 object-contain drop-shadow-sm" alt="Cible d'Investigation" />
          </div>
          <div>
            <div className="text-xs text-indigo-300/70 font-mono">CIBLE D'INVESTIGATION</div>
            <div className="font-bold text-slate-200">{data.targetName || 'Cible Inconnue'}</div>
          </div>
        </div>
        <Handle type="source" position={Position.Right} className="!bg-indigo-500 !w-3 !h-3 !border-2 !border-slate-900" />
      </div>
    );
  }

  const isActive = ['searching', 'mapping', 'analyzing'].includes(data.phase);
  const isDone = data.phase === 'done';
  const colorClass = getStatusColor(data.phase);

  return (
    <div className={`relative w-[280px] p-4 rounded-xl border-2 backdrop-blur-md transition-all duration-500 ${colorClass} ${isActive ? 'shadow-[0_0_20px_-5px_currentColor]' : ''}`}>
      {!data.isStart && <Handle type="target" position={Position.Left} className="!bg-slate-700 !w-3 !h-3 !border-2 !border-slate-900" />}
      
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${isActive ? 'bg-current/20 animate-pulse' : 'bg-current/10'}`}>
             {getIcon(data.id, "w-4 h-4")}
          </div>
          <div>
            <div className="font-bold text-sm text-slate-200">{data.name}</div>
            <div className="text-[10px] font-mono tracking-wider flex items-center gap-1 mt-0.5">
              {isActive && <Loader2 className="w-3 h-3 animate-spin" />}
              {isDone && <CheckCircle2 className="w-3 h-3" />}
              {data.phase === 'error' && <AlertTriangle className="w-3 h-3" />}
              {getStatusLabel(data.phase)}
            </div>
          </div>
        </div>
        
        {data.score !== undefined && isDone && (
          <div className="flex flex-col items-center justify-center bg-slate-950 rounded border border-emerald-500/30 px-2 py-1">
            <span className="text-[10px] text-slate-400 font-mono">RISQUE</span>
            <span className="text-sm font-bold text-emerald-400">{data.score}/10</span>
          </div>
        )}
      </div>

      {/* Terminal / Logs area */}
      <div className="bg-slate-950/80 rounded-lg p-2 h-[80px] overflow-hidden relative border border-white/5 flex flex-col-reverse">
        {data.logs.length === 0 ? (
          <div className="text-xs text-slate-600 font-mono flex h-full items-center justify-center">
            En attente d'instruction...
          </div>
        ) : (
          <div className="space-y-1.5 flex flex-col justify-end min-h-full">
            <AnimatePresence initial={false}>
              {data.logs.slice(-3).map((log, i) => (
                <motion.div
                  key={i + log.timestamp}
                  initial={{ opacity: 0, x: -10, height: 0 }}
                  animate={{ opacity: 1, x: 0, height: 'auto' }}
                  className="text-[10px] font-mono leading-tight flex items-start gap-1.5"
                >
                  <span className="text-slate-500 shrink-0">[{log.timestamp}]</span>
                  <span className={i === 2 ? 'text-slate-300' : 'text-slate-500'}>
                    {log.message}
                  </span>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
        {/* Dither fade effect at top of terminal */}
        <div className="absolute top-0 left-0 right-0 h-4 bg-gradient-to-b from-slate-950/80 to-transparent pointer-events-none" />
      </div>

      <Handle type="source" position={Position.Right} className="!bg-slate-700 !w-3 !h-3 !border-2 !border-slate-900" />
      
      {/* Activity indicator border */}
      {isActive && (
        <div className="absolute inset-0 rounded-xl border-2 border-current opacity-50 animate-ping pointer-events-none" style={{ animationDuration: '2s' }} />
      )}
    </div>
  );
}
