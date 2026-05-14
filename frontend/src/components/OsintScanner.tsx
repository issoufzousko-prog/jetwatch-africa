import { useState } from 'react';
import { UserPlus, AlertCircle, CheckCircle2, Sparkles, Search, Loader2 } from 'lucide-react';
import { api } from '../services/api';

interface VipResult {
  photo_url: string;
  thumbnail: string;
  description: string;
  extract: string;
  message: string;
}

export default function OsintScanner() {
  const [vipName, setVipName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VipResult | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vipName.trim() || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await api.addVIP(vipName.trim());
      setResult(data);
      // Reset name after 8 seconds
      setTimeout(() => {
        setVipName('');
        setResult(null);
      }, 8000);
    } catch (err: any) {
      setError(err.message || 'Erreur lors de la création du profil.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-lg border-b border-glass-border">
      {/* Title */}
      <div className="flex items-center gap-md mb-md">
        <img 
          src="/vip-detect.svg" 
          alt="Détection automatique" 
          className="w-16 h-16 object-contain drop-shadow-[0_0_20px_rgba(41,138,250,0.6)]" 
        />
        <div>
          <h2 className="sp-h3 text-foreground leading-tight">Ajouter un VIP</h2>
          <p className="sp-caption text-muted-foreground mt-1">Détection automatique</p>
        </div>
      </div>

      {/* Single input form */}
      <form onSubmit={handleCreate} className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
        <input
          type="text"
          placeholder="Ex : Cristiano Ronaldo"
          value={vipName}
          onChange={(e) => { setVipName(e.target.value); setError(null); setResult(null); }}
          disabled={loading}
          className="w-full bg-white/[0.04] border border-border-subtle rounded-xl py-2.5 pl-10 pr-24
                     sp-body text-foreground placeholder-text-subtle
                     focus:outline-none focus:border-[#298AFA]/60 focus:bg-white/[0.06] focus:shadow-[0_0_0_3px_rgba(41,138,250,0.08)]
                     transition-all disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={loading || !vipName.trim()}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 px-3 py-1.5
                     bg-gradient-to-r from-[#298AFA] to-[#8B48F9] hover:from-[#3594FA] hover:to-[#9657F9]
                     text-white sp-micro font-semibold rounded-lg transition-all 
                     disabled:opacity-40 disabled:cursor-not-allowed
                     shadow-sm shadow-[#298AFA]/20 hover:shadow-md hover:shadow-[#298AFA]/30
                     active:scale-95"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <UserPlus className="w-4 h-4" />
          )}
        </button>
      </form>

      {/* Loading state */}
      {loading && (
        <div className="mt-3 flex items-center gap-2 p-2.5 rounded-lg bg-[#298AFA]/5 border border-[#298AFA]/10 animate-pulse">
          <div className="w-8 h-8 rounded-full bg-[#298AFA]/20 flex items-center justify-center shrink-0">
            <Loader2 className="w-4 h-4 text-[#298AFA] animate-spin" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="sp-caption text-[#298AFA]">Recherche de {vipName}...</p>
            <p className="sp-micro text-muted-foreground">Analyse Wikipedia en cours</p>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-3 flex items-center gap-2 p-2.5 rounded-lg bg-accent-red/5 border border-accent-red/15">
          <AlertCircle className="w-4 h-4 text-accent-red shrink-0" />
          <p className="sp-caption text-accent-red">{error}</p>
        </div>
      )}

      {/* Success: show found profile */}
      {result && (
        <div className="mt-3 rounded-xl overflow-hidden border border-accent-green/20 bg-gradient-to-br from-accent-green/5 to-transparent">
          <div className="flex items-center gap-3 p-3">
            {/* Auto-found photo */}
            {result.thumbnail ? (
              <img 
                src={result.thumbnail}
                alt={vipName}
                className="w-12 h-12 rounded-full object-cover border-2 border-accent-green/40 shadow-lg shadow-accent-green/10 shrink-0"
              />
            ) : (
              <div className="w-12 h-12 rounded-full bg-accent-blue/10 border-2 border-dashed border-accent-blue/30 flex items-center justify-center shrink-0">
                <UserPlus className="w-5 h-5 text-accent-blue/60" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-accent-green shrink-0" />
                <span className="sp-body-semibold text-accent-green truncate">Profil créé</span>
              </div>
              {result.description && (
                <p className="sp-micro text-muted-foreground truncate mt-0.5">{result.description}</p>
              )}
            </div>
          </div>
          {result.extract && (
            <div className="px-3 pb-3">
              <p className="sp-micro text-text-subtle leading-relaxed line-clamp-2">{result.extract}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
