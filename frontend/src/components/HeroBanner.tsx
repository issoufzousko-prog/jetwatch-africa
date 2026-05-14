import { Suspense } from 'react';
import { ArrowDown, BarChart2, Loader2, Globe, Activity } from 'lucide-react';
import { Canvas } from '@react-three/fiber';
import { Environment, Html } from '@react-three/drei';
import Jet3D from './Jet3D';
import ErrorBoundary from './ErrorBoundary';

interface HeroBannerProps {
  onScrollToContent?: () => void;
}

export default function HeroBanner({ onScrollToContent }: HeroBannerProps) {
  const handleViewCountries = () => {
    const sidebar = document.querySelector('aside');
    if (sidebar) {
      sidebar.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      // On mobile, sidebar might be hidden — scroll down
      window.scrollBy({ top: 400, behavior: 'smooth' });
    }
  };

  const handleViewDashboard = () => {
    if (onScrollToContent) {
      onScrollToContent();
    } else {
      const dashboard = document.getElementById('dashboard-content');
      if (dashboard) {
        dashboard.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else {
        window.scrollBy({ top: 600, behavior: 'smooth' });
      }
    }
  };

  return (
    <div className="relative w-full overflow-visible rounded-2xl bg-gradient-to-br from-[#0c0c10] via-[#0f1118] to-[#0c1016] border border-glass-border shadow-card mb-xl" style={{ minHeight: '320px' }}>

      {/* Background Map */}
      <div
        className="absolute right-0 top-0 w-2/3 h-full opacity-40 mix-blend-screen pointer-events-none"
        style={{
          backgroundImage: 'url(/africa_map_bg.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'right center',
          maskImage: 'linear-gradient(to right, transparent, black 40%)',
          WebkitMaskImage: 'linear-gradient(to right, transparent, black 40%)'
        }}
      />

      {/* Ambient glow */}
      <div className="absolute top-0 left-1/4 w-[400px] h-[300px] bg-[#10b981]/[0.04] rounded-full blur-[120px] pointer-events-none" />

      <div className="relative z-10 flex flex-col lg:flex-row items-center h-full" style={{ minHeight: '320px' }}>
        {/* Text Content - Left Side */}
        <div className="flex-1 flex flex-col items-start text-left p-lg sm:p-xl md:p-2xl max-w-lg z-20">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#10b981]/10 border border-[#10b981]/20 text-[#10b981] text-[10px] font-bold uppercase tracking-[0.15em] mb-md">
            <Activity className="w-3 h-3" />
            Surveillance active
          </div>

          <h2 className="text-2xl sm:text-3xl md:text-4xl font-black text-white tracking-tight leading-[1.1] mb-sm" style={{ fontFamily: 'Inter, sans-serif' }}>
            Tableau de bord
          </h2>

          <p className="text-sm sm:text-base text-gray-400 mb-lg leading-relaxed max-w-sm">
            Sélectionnez un pays dans la barre latérale pour consulter son dossier de renseignement complet.
          </p>

          <div className="flex flex-col sm:flex-row items-center gap-sm w-full sm:w-auto">
            <button
              onClick={handleViewCountries}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 bg-[#10b981] hover:bg-[#059669] text-white text-sm font-semibold rounded-lg transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-[#10b981]/20 active:scale-[0.98]"
            >
              <Globe className="w-4 h-4" />
              Voir les pays
            </button>
            <button
              onClick={handleViewDashboard}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 bg-transparent hover:bg-white/5 text-white text-sm font-medium rounded-lg border border-white/15 hover:border-white/25 transition-all hover:-translate-y-0.5 active:scale-[0.98]"
            >
              <ArrowDown className="w-4 h-4" />
              Données du pays
            </button>
          </div>
        </div>

        {/* 3D Jet Model - Full Banner Overlay for breakout effect */}
        <div className="jet-3d-overlay absolute z-30 pointer-events-none" style={{ top: 0, left: 0, right: 0, bottom: '-60px' }}>
          <ErrorBoundary fallbackMessage="Impossible de charger le modèle 3D du jet.">
            <Canvas
              camera={{ position: [0, 0.5, 6], fov: 40 }}
              className="w-full h-full"
              style={{ pointerEvents: 'none' }}
              onCreated={({ gl }) => {
                // R3F attache ses event listeners sur le canvas DOM après le render React.
                // On force pointer-events:none directement sur l'élément <canvas> pour
                // s'assurer qu'il ne capte aucun clic, même après l'init de R3F.
                gl.domElement.style.pointerEvents = 'none';
                gl.domElement.style.touchAction = 'none';
              }}
            >
              <Suspense fallback={
                <Html center>
                  <div className="flex flex-col items-center justify-center text-[#10b981]">
                    <Loader2 className="w-8 h-8 animate-spin mb-2" />
                  </div>
                </Html>
              }>
                <ambientLight intensity={0.8} />
                <directionalLight position={[5, 8, 10]} intensity={2.5} color="#ffffff" castShadow />
                <directionalLight position={[-5, 3, 5]} intensity={1.5} color="#10b981" />
                <directionalLight position={[0, 5, -5]} intensity={1.0} color="#e2e8f0" />
                <spotLight position={[3, 5, 8]} intensity={2} angle={0.6} penumbra={0.5} color="#ffffff" />

                <Environment preset="city" />

                <Jet3D />

              </Suspense>
            </Canvas>
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
}
