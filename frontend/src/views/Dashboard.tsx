import { useState, useEffect } from 'react';
import ScoreGauge from '../components/ScoreGauge';
import MetricsGrid from '../components/MetricsGrid';
import FlightsTable from '../components/FlightsTable';
import HeroBanner from '../components/HeroBanner';
import OsintDiscovery from '../components/OsintDiscovery';
import FleetReport from '../components/FleetReport';
import AiAnalyst from '../components/AiAnalyst';
import { api } from '../services/api';
import { LayoutDashboard, ShieldAlert, Plane } from 'lucide-react';

interface DashboardProps {
  selectedCountry: string | null;
}

type TabType = 'overview' | 'osint' | 'fleet';

export default function Dashboard({ selectedCountry }: DashboardProps) {
  const [loading, setLoading] = useState(false);
  const [scoreData, setScoreData] = useState<any>(null);
  const [flights, setFlights] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  // Reset tab when country changes
  useEffect(() => {
    setActiveTab('overview');
  }, [selectedCountry]);

  useEffect(() => {
    if (!selectedCountry) return;
    
    let isMounted = true;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const scoreRes = await api.getScore(selectedCountry);
        if (!scoreRes) {
          if (isMounted) setError(`Aucun vol enregistré pour le moment pour ${selectedCountry}`);
        } else {
          // Mapper les données API vers les props attendus par les composants
          if (isMounted) {
            setScoreData({
              pays: scoreRes.pays,
              dirigeant: scoreRes.dirigeant,
              niveau: scoreRes.niveau,
              score_final: scoreRes.score_global,
              equivalence_foyer_annees: Math.round(scoreRes.co2_kg / 1000 / 0.13), // 1 foyer fr = ~0.13t/an (simpliste)
              total_vols: scoreRes.total_vols,
              total_heures: scoreRes.total_heures,
              co2_kg: scoreRes.co2_kg,
              cout_usd: scoreRes.cout_usd,
              ratio_suspects: scoreRes.ratio_suspects,
              taux_ads_b: scoreRes.taux_ads_b
            });
          }
        }
        
        const flightsRes = await api.getFlights(selectedCountry);
        if (isMounted) {
          setFlights(flightsRes || []);
        }
      } catch (err) {
        if (isMounted) setError("Erreur lors de la récupération des données.");
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    
    fetchData();
    
    return () => {
      isMounted = false;
    };
  }, [selectedCountry]);

  if (!selectedCountry) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <p className="sp-h4 text-muted-foreground mb-2xs">Sélectionnez une cible</p>
          <p className="sp-caption text-text-subtle">pour afficher son dossier de renseignement.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-xl">
      <HeroBanner />
      
      {/* Header & Tabs Navigation */}
      <div id="dashboard-content" className="flex flex-col md:flex-row md:items-end justify-between gap-md border-b border-glass-border pb-sm">
        <div>
          <h2 className="sp-h3 text-foreground">Tableau de Bord</h2>
          <p className="sp-caption text-muted-foreground mt-3xs">
            Dossier de renseignement : <span className="notranslate">{selectedCountry}</span>
          </p>
        </div>
        
        <div className="flex bg-black/40 p-1 rounded-lg border border-glass-border backdrop-blur-md">
          <button
            onClick={() => setActiveTab('overview')}
            className={`flex items-center gap-2 px-md py-sm rounded-md transition-all sp-caption ${
              activeTab === 'overview'
                ? 'bg-white/10 text-white shadow-sm'
                : 'text-muted-foreground hover:text-white hover:bg-white/5'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span className="hidden sm:inline">Vue d'ensemble</span>
          </button>
          
          <button
            onClick={() => setActiveTab('osint')}
            className={`flex items-center gap-2 px-md py-sm rounded-md transition-all sp-caption ${
              activeTab === 'osint'
                ? 'bg-accent-blue/20 text-accent-blue border border-accent-blue/30 shadow-sm shadow-accent-blue/10'
                : 'text-muted-foreground hover:text-accent-blue hover:bg-white/5'
            }`}
          >
            <ShieldAlert className="w-4 h-4" />
            <span className="hidden sm:inline">OSINT & IA</span>
          </button>
          
          <button
            onClick={() => setActiveTab('fleet')}
            className={`flex items-center gap-2 px-md py-sm rounded-md transition-all sp-caption ${
              activeTab === 'fleet'
                ? 'bg-white/10 text-white shadow-sm'
                : 'text-muted-foreground hover:text-white hover:bg-white/5'
            }`}
          >
            <Plane className="w-4 h-4" />
            <span className="hidden sm:inline">Rapport de Flotte</span>
          </button>
        </div>
      </div>

      {/* Tab Content Area */}
      <div className="animate-in fade-in duration-500">
        {activeTab === 'overview' && (
          <div>
            {loading ? (
              <div className="flex items-center justify-center py-3xl text-muted-foreground sp-body animate-pulse">
                Chargement des métriques...
              </div>
            ) : error ? (
              <div className="glass-card p-xl text-center border-accent-red/30">
                <p className="sp-h5 text-accent-red mb-2xs">{error}</p>
                <p className="sp-caption text-muted-foreground">Les données de vol ne sont pas encore disponibles.</p>
              </div>
            ) : scoreData ? (
              <div className="flex flex-col gap-xl">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-xl">
                  <div className="col-span-1">
                    <ScoreGauge data={scoreData} />
                  </div>
                  <div className="col-span-1 lg:col-span-2">
                    <MetricsGrid data={scoreData} />
                  </div>
                </div>
                <FlightsTable flights={flights} />
              </div>
            ) : null}
          </div>
        )}

        {activeTab === 'osint' && (
          <div className="flex flex-col gap-xl">
            <OsintDiscovery country={selectedCountry} />
            <AiAnalyst country={selectedCountry} flights={flights} />
          </div>
        )}

        {activeTab === 'fleet' && (
          <div>
            <FleetReport country={selectedCountry} />
          </div>
        )}
      </div>
    </div>
  );
}
