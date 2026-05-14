import { useState } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Zap, Brain, Code2, Cpu } from 'lucide-react';
import InvestigationButton from './InvestigationButton';

export interface DetectiveModel {
  id: string;
  name: string;
  brand: string;
  specialty: string;
  size: string;
  description: string;
  icon: string; // path to image
  color: string; // accent color
}

export const DETECTIVE_MODELS: DetectiveModel[] = [
  {
    id: 'groq/llama-3.3-70b-versatile',
    name: 'Llama 3.3',
    brand: 'Meta',
    specialty: 'Raisonnement / Logique',
    size: '70B',
    description: 'Le modèle le plus performant pour l\'investigation complexe, la synthèse multi-documents et la génération du graphe de connaissances.',
    icon: '/logos/llama.png',
    color: '#818cf8', // indigo
  },
  {
    id: 'groq/mixtral-8x7b-32768',
    name: 'Mixtral 8x7B',
    brand: 'Mistral AI',
    specialty: 'Fiabilité / Structuration',
    size: '8x7B',
    description: 'Architecture MoE (Mixture of Experts). Excellent pour l\'extraction factuelle et l\'analyse de schémas de blanchiment.',
    icon: '/logos/mistralai.png',
    color: '#fb923c', // orange
  },
  {
    id: 'groq/llama-3.1-8b-instant',
    name: 'Llama 3.1',
    brand: 'Meta',
    specialty: 'Vitesse / Instantané',
    size: '8B',
    description: 'Modèle léger et ultra-rapide. Parfait pour une analyse préliminaire immédiate et un balayage rapide des données OSINT.',
    icon: '/logos/llama.png',
    color: '#facc15', // yellow
  },
  {
    id: 'groq/gemma2-9b-it',
    name: 'Gemma 2',
    brand: 'Google',
    specialty: 'Précision / Code',
    size: '9B',
    description: 'Spécialisé dans le parsing de structures complexes et le croisement précis d\'informations financières.',
    icon: '/logos/gemma.jpg',
    color: '#34d399', // emerald
  },
];

interface ModelSelectorProps {
  onSelect: (model: DetectiveModel) => void;
  onCancel?: () => void;
}

export default function ModelSelector({ onSelect, onCancel }: ModelSelectorProps) {
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="w-full"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h4 className="sp-h5 text-foreground mb-1">Choisir le modèle Détective</h4>
          <p className="sp-caption text-muted-foreground max-w-lg">
            Cliquez sur un modèle pour lancer l'investigation automatiquement.
          </p>
        </div>
        {onCancel && (
          <button
            onClick={onCancel}
            className="sp-caption text-slate-400 hover:text-slate-200 transition-colors px-4 py-2 border border-slate-700/50 rounded-lg hover:bg-slate-800"
          >
            Annuler
          </button>
        )}
      </div>

      {/* OSINT Agent info banner */}
      <div className="flex items-center gap-3 p-3 mb-5 rounded-lg border border-blue-500/20 bg-blue-500/5">
        <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center shrink-0">
          <svg viewBox="0 0 24 24" className="w-4 h-4 text-blue-400" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
          </svg>
        </div>
        <div>
          <p className="sp-caption font-semibold text-blue-300">Agent OSINT fixe : Command R+ (Cohere)</p>
          <p className="sp-micro text-slate-400">Recherche autonome dans les bases de données publiques (Aleph, OCCRP, presse, patrimoine)</p>
        </div>
      </div>

      {/* Model cards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
        {DETECTIVE_MODELS.map((model) => {
          const isHovered = hovered === model.id;
          return (
            <motion.button
              key={model.id}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => onSelect(model)}
              onMouseEnter={() => setHovered(model.id)}
              onMouseLeave={() => setHovered(null)}
              className="relative text-left p-4 rounded-xl border border-slate-700/60 bg-slate-900/40 hover:bg-slate-800/80 transition-all duration-200 group"
              style={{
                borderColor: isHovered ? model.color : undefined,
                boxShadow: isHovered ? `0 0 20px -5px ${model.color}40` : undefined,
              }}
            >

              {/* Icon + Name */}
              <div className="flex items-center gap-2.5 mb-2">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center overflow-hidden bg-white/5 p-1"
                >
                  <img 
                    src={model.icon} 
                    alt={model.name} 
                    className="w-full h-full object-contain"
                  />
                </div>
                <div>
                  <p className="font-semibold text-sm text-white leading-tight">{model.name}</p>
                  <p className="text-xs text-slate-500">{model.brand}</p>
                </div>
              </div>

              {/* Specialty + Size */}
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="sp-micro px-2 py-0.5 rounded font-mono font-semibold"
                  style={{ backgroundColor: `${model.color}18`, color: model.color, border: `1px solid ${model.color}30` }}
                >
                  {model.size}
                </span>
                <span className="sp-micro text-slate-400">{model.specialty}</span>
              </div>

              {/* Description */}
              <p className="sp-micro text-slate-500 leading-relaxed">{model.description}</p>
            </motion.button>
          );
        })}
      </div>

    </motion.div>
  );
}
