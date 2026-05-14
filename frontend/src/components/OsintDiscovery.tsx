import { useState, useEffect } from 'react';
import { Search, CheckCircle2, AlertCircle, ShieldAlert, Plus } from 'lucide-react';
import { api } from '../services/api';
import Loader from './Loader';

interface OsintDiscoveryProps {
  country: string;
}

export default function OsintDiscovery({ country }: OsintDiscoveryProps) {
  const [loading, setLoading] = useState(false);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [prefixes, setPrefixes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [addingIds, setAddingIds] = useState<Set<string>>(new Set());
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set());
  const [addError, setAddError] = useState<string | null>(null);

  // Reset state when country changes
  useEffect(() => {
    setCandidates([]);
    setPrefixes([]);
    setError(null);
    setHasSearched(false);
    setAddingIds(new Set());
    setAddedIds(new Set());
  }, [country]);

  const handleDiscover = async () => {
    setLoading(true);
    setError(null);
    setHasSearched(true);
    try {
      const res = await api.osintDiscover(country);
      setPrefixes(res.prefixes || []);
      setCandidates(res.candidats || []);
    } catch (err: any) {
      setError(err.message || 'Erreur lors de la découverte OSINT');
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (cand: any) => {
    if (!cand || !cand.icao24) {
      setAddError('Données invalides pour cet avion.');
      return;
    }
    setAddError(null);
    setAddingIds(prev => new Set(prev).add(cand.icao24));
    try {
      await api.addJetToFleet({
        pays: country,
        icao24: String(cand.icao24),
        tail_number: String(cand.tail_number || 'INCONNU'),
        description: `${String(cand.manufacturer || 'Inconnu')} ${String(cand.model || 'Inconnu')} (${String(cand.operator || 'Inconnu')})`
      });
      setAddedIds(prev => new Set(prev).add(cand.icao24));
      setAddError(null);
    } catch (err: any) {
      console.error('[JetWatch] Erreur ajout flotte:', err);
      const msg = err?.message || "Erreur lors de l'ajout au radar.";
      setAddError(`${cand.tail_number}: ${msg}`);
    } finally {
      setAddingIds(prev => {
        const next = new Set(prev);
        next.delete(cand.icao24);
        return next;
      });
    }
  };

  return (
    <div className="glass-card p-lg mb-xl">
      <div className="flex items-center justify-between mb-sm">
        <div className="flex items-center gap-sm">
          <ShieldAlert className="w-5 h-5 text-accent-orange" />
          <h2 className="sp-h5 text-foreground">Découverte OSINT Automatisée</h2>
        </div>
        <button
          onClick={handleDiscover}
          disabled={loading}
          className="flex items-center gap-2 px-md py-1.5 bg-accent-orange/20 hover:bg-accent-orange/30 text-accent-orange border border-accent-orange/30 rounded-md transition-colors disabled:opacity-50"
        >
          {loading ? (
            <div className="w-4 h-4 border-2 border-accent-orange border-t-transparent rounded-full animate-spin" />
          ) : (
            <Search className="w-4 h-4" />
          )}
          <span className="sp-body-semibold">Scraper les registres pour {country}</span>
        </button>
      </div>

      <p className="sp-caption text-muted-foreground mb-md">
        Le moteur de recherche va scanner la base de données globale (OpenSky) à la recherche de jets VIP (Dassault, Gulfstream, Boeing...) associés à : <span className="text-foreground font-semibold">{country}</span>.
      </p>

      {error && !loading && (
        <div className="p-sm bg-accent-red/10 border border-accent-red/20 rounded-md flex items-center gap-xs mb-md">
          <AlertCircle className="w-4 h-4 text-accent-red" />
          <p className="sp-caption text-accent-red">{error}</p>
        </div>
      )}

      {addError && (
        <div className="p-sm bg-accent-orange/10 border border-accent-orange/20 rounded-md flex items-center justify-between gap-xs mb-md animate-in fade-in duration-300">
          <div className="flex items-center gap-xs">
            <AlertCircle className="w-4 h-4 text-accent-orange shrink-0" />
            <p className="sp-caption text-accent-orange">{addError}</p>
          </div>
          <button onClick={() => setAddError(null)} className="text-accent-orange hover:text-white sp-micro px-2">✕</button>
        </div>
      )}

      {loading && (
        <div className="py-2xl">
          <Loader message={`Veuillez patienter : Scraper les registres pour ${country}`} />
        </div>
      )}

      {hasSearched && !loading && !error && (
        <div className="space-y-sm">
          <div className="flex items-center gap-2 text-muted-foreground sp-caption">
            <span>Préfixe(s) OACI détecté(s) :</span>
            {prefixes.map(p => (
              <span key={p} className="px-xs py-0.5 bg-white/5 rounded border border-white/10">{p}-XXX</span>
            ))}
          </div>

          {candidates.length === 0 ? (
            <div className="p-xl text-center border border-dashed border-glass-border rounded-lg mt-md">
              <p className="sp-body text-muted-foreground">Aucun jet gouvernemental/VIP trouvé pour {country}.</p>
            </div>
          ) : (
            <div className="mt-md border border-glass-border rounded-lg overflow-hidden">
              <table className="w-full text-left">
                <thead className="bg-black/40 border-b border-glass-border">
                  <tr>
                    <th className="p-sm sp-micro text-muted-foreground">Immatriculation</th>
                    <th className="p-sm sp-micro text-muted-foreground">Modèle</th>
                    <th className="p-sm sp-micro text-muted-foreground hidden md:table-cell">Opérateur</th>
                    <th className="p-sm sp-micro text-muted-foreground text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-glass-border">
                  {candidates.map(cand => {
                    const isAdding = addingIds.has(cand.icao24);
                    const isAdded = addedIds.has(cand.icao24);
                    return (
                      <tr key={`${cand?.icao24}-${cand?.tail_number}`} className="hover:bg-white/[0.02] transition-colors">
                        <td className="p-sm">
                          <span className="sp-body-semibold text-accent-blue">{cand?.tail_number ? String(cand.tail_number) : 'INCONNU'}</span>
                          <div className="flex items-center gap-2 mt-0.5">
                            {cand?.icao24 && String(cand.icao24).startsWith('web_') ? (
                              <span className="sp-micro text-accent-orange font-mono bg-accent-orange/10 px-1 rounded border border-accent-orange/20">OSINT WEB</span>
                            ) : (
                              <div className="sp-micro text-muted-foreground font-mono">HEX: {cand?.icao24 ? String(cand.icao24).toUpperCase() : 'N/A'}</div>
                            )}
                          </div>
                        </td>
                        <td className="p-sm">
                          <span className="sp-caption text-foreground">{cand?.manufacturer ? String(cand.manufacturer) : 'Inconnu'}</span>
                          <div className="sp-caption text-foreground">{cand?.model ? String(cand.model) : 'Inconnu'}</div>
                        </td>
                        <td className="p-sm hidden md:table-cell">
                          <span className="sp-caption text-muted-foreground">{cand?.operator ? String(cand.operator) : '—'}</span>
                        </td>
                        <td className="p-sm text-right">
                          {isAdded ? (
                            <span className="inline-flex items-center gap-1 text-accent-green sp-caption px-sm py-1 bg-accent-green/10 rounded">
                              <CheckCircle2 className="w-3 h-3" /> <span>Ajouté</span>
                            </span>
                          ) : (
                            <button
                              onClick={() => handleAdd(cand)}
                              disabled={isAdding}
                              className="inline-flex items-center gap-1 bg-white/10 hover:bg-white/20 text-foreground sp-caption px-sm py-1 rounded transition-colors disabled:opacity-50"
                            >
                              {isAdding ? <span>Ajout...</span> : <span><Plus className="w-3 h-3 inline-block" /> Ajouter au Radar</span>}
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
