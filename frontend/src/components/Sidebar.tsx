import { useState, useEffect } from 'react';
import { Search, CheckCircle2, ChevronRight } from 'lucide-react';
import { api } from '../services/api';
import { getProfileImageUrl, getFlagUrl } from '../utils/flags';
import OsintScanner from './OsintScanner';

interface SidebarProps {
  selectedCountry: string | null;
  onSelect: (country: string) => void;
}

interface PaysInfo {
  pays: string;
  dirigeant: string;
  photo_url?: string;
  type_regime?: string;
  jets_verifies: number;
}

type NiveauType = 'critique' | 'eleve' | 'modere' | 'normal';

const niveauConfig: Record<NiveauType, { label: string; classes: string }> = {
  critique: { label: 'CRITIQUE', classes: 'bg-accent-red/10 text-accent-red border-accent-red/20' },
  eleve:    { label: 'ÉLEVÉ',    classes: 'bg-accent-orange/10 text-accent-orange border-accent-orange/20' },
  modere:   { label: 'MODÉRÉ',   classes: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  normal:   { label: 'NORMAL',   classes: 'bg-accent-green/10 text-accent-green border-accent-green/20' },
};

function getNiveau(pays: string): NiveauType {
  // Optionnellement, récupérer ça de l'API s'il est dispo, sinon on utilise 'normal'
  return "normal";
}

export default function Sidebar({ selectedCountry, onSelect }: SidebarProps) {
  const [countries, setCountries] = useState<PaysInfo[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    api.getCountries().then(data => {
      if (isMounted) {
        setCountries(data);
        setLoading(false);
      }
    }).catch(e => {
      console.error(e);
      if (isMounted) setLoading(false);
    });
    return () => { isMounted = false; };
  }, []);

  const filtered = countries.filter(c =>
    c.pays.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.dirigeant.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <aside className="glass-card h-full flex flex-col overflow-hidden">
      {/* VIP Creation Section */}
      <OsintScanner />

      {/* Header */}
      <div className="p-lg border-b border-glass-border">
        <h2 className="sp-h5 text-foreground mb-md">Cibles surveillées (États & VIPs)</h2>
        <div className="relative">
          <Search className="absolute left-md top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Rechercher..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-white/[0.04] border border-border-subtle rounded-lg py-xs pl-3xl pr-md 
                       sp-body text-foreground placeholder-text-subtle
                       focus:outline-none focus:border-glass-border-hover focus:bg-white/[0.06] 
                       transition-all"
          />
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-sm space-y-2xs">
        {loading ? (
          <div className="p-xl text-center text-muted-foreground sp-caption animate-pulse">
            Chargement de la flotte...
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-xl text-center text-muted-foreground sp-caption">
            Aucun résultat
          </div>
        ) : (
          filtered.map(c => {
            const isActive = selectedCountry === c.pays;
            const niveau = getNiveau(c.pays);
            const config = niveauConfig[niveau];
            const isVip = getFlagUrl(c.pays) === null;
            const imgUrl = getProfileImageUrl(c.pays, c.photo_url);
            return (
              <button
                key={c.pays}
                onClick={() => onSelect(c.pays)}
                className={`sidebar-item group ${isActive ? 'sidebar-item-active' : ''}`}
              >
                {/* Avatar: Photo VIP (cercle) ou Drapeau (rectangulaire) */}
                <img 
                  src={imgUrl} 
                  alt={c.pays} 
                  className={`shrink-0 object-cover ${
                    isVip 
                      ? 'w-8 h-8 rounded-full border-2 border-accent-blue/40 shadow-sm shadow-accent-blue/20' 
                      : 'w-8 h-6 rounded-sm'
                  }`}
                  onError={(e) => {
                    const target = e.target as HTMLImageElement;
                    if (target.dataset.failed) return;
                    target.dataset.failed = 'true';
                    target.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(c.pays)}&background=1e293b&color=fff&rounded=true`;
                  }}
                />
                
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-xs">
                    <span className="sp-body-semibold text-foreground truncate notranslate">{c.pays}</span>
                    <span className={`sp-micro px-xs py-3xs rounded-full border shrink-0 ${config.classes}`}>
                      {config.label}
                    </span>
                  </div>
                  <div className="flex items-center justify-between mt-3xs">
                    <span className="sp-caption text-muted-foreground truncate">{c.dirigeant}</span>
                    <span className="sp-data-sm text-muted-foreground flex items-center gap-3xs shrink-0">
                      {c.jets_verifies > 0 && (
                        <>
                          <CheckCircle2 className="w-3 h-3 text-accent-blue" />
                          {c.jets_verifies}
                        </>
                      )}
                    </span>
                  </div>
                </div>
                
                {/* Arrow */}
                <ChevronRight className={`w-4 h-4 shrink-0 transition-all ${
                  isActive ? 'text-accent-red translate-x-0' : 'text-text-subtle -translate-x-1 opacity-0 group-hover:opacity-100 group-hover:translate-x-0'
                }`} />
              </button>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="p-lg border-t border-glass-border">
        <div className="flex items-center justify-between">
          <span className="sp-caption text-muted-foreground">{countries.length} cibles</span>
          <span className="sp-micro text-accent-green flex items-center gap-3xs">
            <span className="relative flex size-[6px]">
              <span className="animate-ping-slow absolute inline-flex h-full w-full rounded-full bg-accent-green opacity-75" />
              <span className="relative inline-flex rounded-full size-[6px] bg-accent-green" />
            </span>
            En ligne
          </span>
        </div>
      </div>
    </aside>
  );
}
