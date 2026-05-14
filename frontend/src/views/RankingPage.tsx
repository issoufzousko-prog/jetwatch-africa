import { useState, useEffect } from 'react';
import { Trophy, ChevronUp, ChevronDown, Search } from 'lucide-react';
import { api } from '../services/api';
import { getProfileImageUrl, getFlagUrl } from '../utils/flags';

interface CountryRank {
  rank?: number;
  pays: string;
  flag: string;
  photo_url?: string;
  dirigeant: string;
  score_global: number;
  niveau: 'CRITIQUE' | 'ÉLEVÉ' | 'MODÉRÉ' | 'NORMAL' | 'N/A';
  total_vols: number;
  vols_officiels: number;
  vols_personnels: number;
  co2_kg: number;
  statut: string;
}

const niveauConfig: Record<string, any> = {
  'CRITIQUE': { label: 'CRITIQUE', bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/20', bar: 'bg-red-500' },
  'ÉLEVÉ':    { label: 'ÉLEVÉ',    bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/20', bar: 'bg-orange-500' },
  'MODÉRÉ':   { label: 'MODÉRÉ',   bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/20', bar: 'bg-yellow-500' },
  'NORMAL':   { label: 'NORMAL',   bg: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/20', bar: 'bg-green-500' },
  'N/A':      { label: 'N/A',      bg: 'bg-gray-500/10', text: 'text-gray-400', border: 'border-gray-500/20', bar: 'bg-gray-500' },
};

const fmt = (n: number) => new Intl.NumberFormat('fr-FR').format(n);

function getImageForTarget(pays: string, photoUrl?: string) {
  return getProfileImageUrl(pays, photoUrl);
}

export default function RankingPage() {
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<keyof CountryRank>('score_global');
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');
  const [rankingData, setRankingData] = useState<CountryRank[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await api.getClassement();
        // Ajouter flag
        const formattedData = data.map((item: any) => ({
          ...item,
          photo_url: item.photo_url || '',
          flag: getImageForTarget(item.pays, item.photo_url),
          // S'assurer que le niveau correspond aux clés
          niveau: item.niveau.replace(/🔴 |🟠 |🟡 |🟢 /g, '').toUpperCase()
        }));
        
        // Trier par score global desc pour avoir le rank
        formattedData.sort((a: any, b: any) => b.score_global - a.score_global);
        
        // Assigner le rank
        formattedData.forEach((item: any, idx: number) => {
          item.rank = item.score_global > 0 ? idx + 1 : '-';
        });
        
        setRankingData(formattedData);
      } catch (e) {
        console.error("Failed to load ranking", e);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchData();
    const intervalId = setInterval(fetchData, 30000); // Poll every 30s
    return () => clearInterval(intervalId);
  }, []);

  const handleSort = (key: keyof CountryRank) => {
    if (sortKey === key) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const sorted = [...rankingData]
    .filter(c => c.pays.toLowerCase().includes(search.toLowerCase()))
    .sort((a: any, b: any) => sortDir === 'desc' ? b[sortKey] - a[sortKey] : a[sortKey] - b[sortKey]);

  const maxScore = Math.max(100, ...rankingData.map(c => c.score_global));

  const SortIcon = ({ col }: { col: keyof CountryRank }) => {
    if (sortKey !== col) return <ChevronDown className="w-3 h-3 opacity-30" />;
    return sortDir === 'desc' ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />;
  };

  return (
    <div className="flex flex-col gap-xl w-full">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-md">
        <div>
          <div className="flex items-center gap-sm mb-2xs">
            <div className="p-xs rounded-lg bg-accent-orange/10">
              <Trophy className="w-5 h-5 text-accent-orange" />
            </div>
            <h2 className="sp-h2 text-foreground">Classement Live</h2>
          </div>
          <p className="sp-body text-muted-foreground">
            Classement temps réel des dirigeants africains par indice d'opacité aérienne
          </p>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Rechercher un pays..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-white/[0.04] border border-glass-border rounded-lg py-2 pl-9 pr-4 sp-body text-foreground placeholder-text-subtle focus:outline-none focus:border-glass-border-hover transition-all"
          />
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-md">
        {[
          { label: 'Pays surveillés', value: rankingData.length.toString(), color: 'text-accent-blue' },
          { label: 'Vols Officiels', value: fmt(rankingData.reduce((s, c) => s + (c.vols_officiels || 0), 0)), color: 'text-accent-green' },
          { label: 'Vols Personnels', value: fmt(rankingData.reduce((s, c) => s + (c.vols_personnels || 0), 0)), color: 'text-accent-red' },
          { label: 'CO2 total (t)', value: `${fmt(rankingData.reduce((s, c) => s + (c.co2_kg || 0) / 1000, 0))}t`, color: 'text-accent-orange' },
        ].map((card, i) => (
          <div key={i} className="glass-card p-lg">
            <p className="sp-micro text-muted-foreground uppercase tracking-wider mb-xs">{card.label}</p>
            <p className={`sp-h3 ${card.color} tabular-nums`}>{card.value}</p>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[800px]">
            <thead>
              <tr className="border-b border-glass-border">
                <th className="text-left sp-micro text-muted-foreground uppercase tracking-wider p-4 pb-3 w-12">#</th>
                <th className="text-left sp-micro text-muted-foreground uppercase tracking-wider p-4 pb-3">Pays</th>
                <th className="sp-micro text-muted-foreground uppercase tracking-wider p-4 pb-3 hidden sm:table-cell">
                  <button onClick={() => handleSort('score_global')} className="flex items-center gap-1 hover:text-foreground transition-colors">
                    Score <SortIcon col="score_global" />
                  </button>
                </th>
                <th className="text-center sp-micro text-muted-foreground uppercase tracking-wider p-4 pb-3">Niveau</th>
                <th className="sp-micro text-muted-foreground uppercase tracking-wider p-4 pb-3">
                  <button onClick={() => handleSort('total_vols')} className="flex items-center gap-1 hover:text-foreground transition-colors">
                    Total Vols <SortIcon col="total_vols" />
                  </button>
                </th>
                <th className="sp-micro text-muted-foreground uppercase tracking-wider p-4 pb-3 hidden md:table-cell">
                  <button onClick={() => handleSort('vols_officiels')} className="flex items-center gap-1 hover:text-foreground transition-colors">
                    Officiels <SortIcon col="vols_officiels" />
                  </button>
                </th>
                <th className="sp-micro text-muted-foreground uppercase tracking-wider p-4 pb-3 hidden md:table-cell">
                  <button onClick={() => handleSort('vols_personnels')} className="flex items-center gap-1 text-red-400 hover:text-red-300 transition-colors">
                    Personnels <SortIcon col="vols_personnels" />
                  </button>
                </th>
                <th className="sp-micro text-muted-foreground uppercase tracking-wider p-4 pb-3 hidden lg:table-cell">
                  <button onClick={() => handleSort('co2_kg')} className="flex items-center gap-1 hover:text-foreground transition-colors">
                    CO2 (Tonnes) <SortIcon col="co2_kg" />
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-muted-foreground sp-body">
                    Chargement du classement en direct...
                  </td>
                </tr>
              ) : sorted.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-muted-foreground sp-body">
                    Aucune donnée disponible.
                  </td>
                </tr>
              ) : sorted.map((c) => {
                const cfg = niveauConfig[c.niveau] || niveauConfig['N/A'];
                return (
                  <tr key={c.pays} className="border-b border-glass-border last:border-0 hover:bg-white/[0.03] transition-colors group cursor-pointer">
                    {/* Rank */}
                    <td className="p-4">
                      <span className={`sp-data font-bold ${typeof c.rank === 'number' && c.rank <= 3 ? 'text-accent-orange' : 'text-muted-foreground'}`}>
                        {c.rank}
                      </span>
                    </td>

                    {/* Country */}
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <img 
                          src={c.flag} 
                          alt={c.pays} 
                          className={`object-cover shadow-sm ${
                            c.photo_url ? 'w-8 h-8 rounded-full border-2 border-accent-blue/40' : 'w-8 h-6 rounded-sm'
                          }`}
                          onError={(e) => { 
                            const target = e.target as HTMLImageElement;
                            if (target.dataset.failed) return;
                            target.dataset.failed = "true";
                            target.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(c.pays)}&background=1e293b&color=fff&rounded=true`;
                          }}
                        />
                        <div>
                          <p className="sp-body-semibold text-foreground notranslate">{c.pays}</p>
                          <p className="sp-caption text-muted-foreground">{c.dirigeant}</p>
                        </div>
                      </div>
                    </td>

                    {/* Score bar */}
                    <td className="p-4 hidden sm:table-cell">
                      <div className="flex items-center gap-3">
                        <span className="sp-data text-foreground font-bold w-8">{c.score_global}</span>
                        <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden max-w-[120px]">
                          <div
                            className={`h-full rounded-full ${cfg.bar} transition-all duration-500`}
                            style={{ width: `${(c.score_global / maxScore) * 100}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* Badge */}
                    <td className="p-4 text-center">
                      <span className={`${cfg.bg} ${cfg.text} border ${cfg.border} px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider whitespace-nowrap`}>
                        {cfg.label}
                      </span>
                    </td>

                    {/* Total Vols */}
                    <td className="p-4">
                      <span className="sp-data text-foreground">{c.total_vols}</span>
                    </td>

                    {/* Vols Officiels */}
                    <td className="p-4 hidden md:table-cell">
                      <span className="sp-data text-green-400">{c.vols_officiels}</span>
                    </td>

                    {/* Vols Personnels */}
                    <td className="p-4 hidden md:table-cell">
                      <span className="sp-data text-red-400">{c.vols_personnels}</span>
                    </td>

                    {/* CO2 */}
                    <td className="p-4 hidden lg:table-cell">
                      <span className="sp-data text-muted-foreground">{fmt(Math.round(c.co2_kg / 1000))}t</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
