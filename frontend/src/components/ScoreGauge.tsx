import { useEffect, useState, useRef } from 'react';

interface ScoreGaugeProps {
  data: {
    pays: string;
    dirigeant: string;
    regime?: string;
    niveau: string;
    score_final: number;
    equivalence_foyer_annees: number;
  };
}

function useCountUp(target: number, duration = 1200) {
  const [count, setCount] = useState(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const start = performance.now();
    const step = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
      setCount(Math.round(eased * target));
      if (progress < 1) rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return count;
}

export default function ScoreGauge({ data }: ScoreGaugeProps) {
  const score = data.score_final || 0;
  const animatedScore = useCountUp(score);

  const niveauStr = data.niveau || "INCONNU";
  const cleanNiveau = niveauStr.replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}]/gu, '').trim();

  const isCritique = cleanNiveau.toUpperCase().includes("CRITIQUE");
  const isEleve = cleanNiveau.toUpperCase().includes("ELEV") || cleanNiveau.toUpperCase().includes("ÉLEV");
  const isModere = cleanNiveau.toUpperCase().includes("MODER") || cleanNiveau.toUpperCase().includes("MODÉR");

  let color = "#22c55e";
  let glowClass = "shadow-glow-green";
  let badgeClass = "badge-normal";
  if (isCritique) { color = "#e63946"; glowClass = "shadow-glow-red"; badgeClass = "badge-critique"; }
  else if (isEleve) { color = "#f59e0b"; glowClass = ""; badgeClass = "badge-eleve"; }
  else if (isModere) { color = "#eab308"; glowClass = ""; badgeClass = "badge-modere"; }

  const anneesEquivalent = data.equivalence_foyer_annees || 0;

  // Semi-circle SVG gauge
  const radius = 90;
  const cx = 140;
  const cy = 130;
  const startAngle = Math.PI;
  const endAngle = 0;
  const arcLength = Math.PI * radius;
  const dashOffset = arcLength - (arcLength * score) / 100;

  const describeArc = () => {
    const x1 = cx + radius * Math.cos(startAngle);
    const y1 = cy + radius * Math.sin(startAngle);
    const x2 = cx + radius * Math.cos(endAngle);
    const y2 = cy + radius * Math.sin(endAngle);
    return `M ${x1} ${y1} A ${radius} ${radius} 0 0 1 ${x2} ${y2}`;
  };

  return (
    <div className="glass-card p-xl h-full flex flex-col relative overflow-hidden">
      {/* Background glow */}
      <div
        className="absolute -top-20 left-1/2 -translate-x-1/2 w-[300px] h-[300px] rounded-full opacity-[0.07] blur-[100px] pointer-events-none transition-colors duration-1000"
        style={{ backgroundColor: color }}
      />

      {/* Header */}
      <div className="text-center mb-lg z-10">
        <h3 className="sp-h3 text-foreground notranslate">{data.pays}</h3>
        <p className="sp-body-medium text-muted-foreground mt-3xs">{data.dirigeant}</p>
        {data.regime && (
          <p className="sp-micro text-text-subtle mt-2xs uppercase tracking-wider">{data.regime}</p>
        )}
      </div>

      {/* Gauge */}
      <div className="flex-1 flex flex-col items-center justify-center relative z-10">
        <div className="relative" style={{ width: 280, height: 160 }}>
          <svg viewBox="0 0 280 160" className="w-full h-full overflow-visible">
            <defs>
              <linearGradient id="gauge-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor={color} stopOpacity="0.3" />
                <stop offset="100%" stopColor={color} stopOpacity="1" />
              </linearGradient>
              <filter id="gauge-glow">
                <feGaussianBlur stdDeviation="6" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Background track */}
            <path
              d={describeArc()}
              fill="none"
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="12"
              strokeLinecap="round"
            />

            {/* Foreground arc */}
            <path
              d={describeArc()}
              fill="none"
              stroke="url(#gauge-gradient)"
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={arcLength}
              strokeDashoffset={dashOffset}
              filter="url(#gauge-glow)"
              className="transition-all duration-1000 ease-out"
            />
          </svg>

          {/* Score number */}
          <div className="absolute inset-0 flex flex-col items-center justify-end pb-md">
            <span className="text-5xl font-black text-foreground tracking-tighter tabular-nums leading-none">
              {animatedScore}
            </span>
            <span className="sp-micro text-muted-foreground uppercase tracking-widest mt-xs">
              / 100
            </span>
          </div>
        </div>

        {/* Badge */}
        <div className="mt-lg">
          <span className={badgeClass}>{cleanNiveau}</span>
        </div>
      </div>

      {/* Shock metric */}
      <div className="mt-xl pt-lg border-t border-glass-border z-10">
        <div className="bg-accent-red/[0.06] border border-accent-red/[0.12] rounded-lg p-lg text-center">
          <p className="sp-micro text-muted-foreground uppercase tracking-wider mb-xs">
            Équivalence Émissions CO₂
          </p>
          <p className="sp-body-semibold text-accent-red">
            <span className="text-xl font-bold">= {Math.round(anneesEquivalent).toLocaleString('fr-FR')}</span>{' '}
            années d'un foyer moyen
          </p>
        </div>
      </div>
    </div>
  );
}
