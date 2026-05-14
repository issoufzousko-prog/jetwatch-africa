import { useState, useEffect, useMemo } from 'react';
import { Plane, ArrowRight, BarChart2, Globe, Eye, Lock } from 'lucide-react';
import Hyperspeed from '../components/Hyperspeed';
import ShinyText from '../components/ShinyText';
import MetallicPaint from '../components/MetallicPaint';
import logoBlack from '../assets/logo-black.svg';
import Counter from '../components/Counter';

import { api } from '../services/api';

interface LandingPageProps {
  onLogin: () => void;
}

export default function LandingPage({ onLogin }: LandingPageProps) {
  const [countriesCount, setCountriesCount] = useState(0);
  const [animatedCount, setAnimatedCount] = useState(0);
  const [userCount, setUserCount] = useState(0);

  // Récupérer le nombre réel d'utilisateurs inscrits
  useEffect(() => {
    const fetchUsersCount = async () => {
      try {
        const data = await api.getUsersCount();
        if (typeof data.count === 'number') {
          setUserCount(data.count);
        }
      } catch (error) {
        console.error("Erreur lors de la récupération du nombre d'utilisateurs", error);
      }
    };
    
    fetchUsersCount();
    // Mise à jour toutes les 30 secondes pour le côté "temps réel"
    const interval = setInterval(fetchUsersCount, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    api.getCountries()
      .then(data => {
        if (Array.isArray(data)) setCountriesCount(data.length);
      })
      .catch(() => {});
  }, []);

  // Animate counter
  useEffect(() => {
    if (countriesCount === 0) return;
    let current = 0;
    const step = Math.max(1, Math.floor(countriesCount / 40));
    const timer = setInterval(() => {
      current += step;
      if (current >= countriesCount) {
        current = countriesCount;
        clearInterval(timer);
      }
      setAnimatedCount(current);
    }, 30);
    return () => clearInterval(timer);
  }, [countriesCount]);

  const hyperspeedOptions = useMemo(() => ({
    distortion: 'turbulentDistortion',
    length: 400,
    roadWidth: 10,
    islandWidth: 2,
    lanesPerRoad: 4,
    fov: 90,
    fovSpeedUp: 150,
    speedUp: 2,
    carLightsFade: 0.4,
    totalSideLightSticks: 20,
    lightPairsPerRoadWay: 40,
    shoulderLinesWidthPercentage: 0.05,
    brokenLinesWidthPercentage: 0.1,
    brokenLinesLengthPercentage: 0.5,
    lightStickWidth: [0.12, 0.5] as [number, number],
    lightStickHeight: [1.3, 1.7] as [number, number],
    movingAwaySpeed: [60, 80] as [number, number],
    movingCloserSpeed: [-120, -160] as [number, number],
    carLightsLength: [400 * 0.03, 400 * 0.2] as [number, number],
    carLightsRadius: [0.05, 0.14] as [number, number],
    carWidthPercentage: [0.3, 0.5] as [number, number],
    carShiftX: [-0.8, 0.8] as [number, number],
    carFloorSeparation: [0, 5] as [number, number],
    colors: {
      roadColor: 0x080808,
      islandColor: 0x0a0a0a,
      background: 0x000000,
      shoulderLines: 0xFFFFFF,
      brokenLines: 0xFFFFFF,
      // Custom JetWatch Palette: Reds/Oranges moving away, Greens moving closer
      leftCars: [0xef4444, 0xf97316, 0xb91c1c],
      rightCars: [0x10b981, 0x059669, 0x34d399],
      sticks: 0x3b82f6,
    }
  }), []);

  return (
    <div className="dark min-h-svh bg-black text-white overflow-hidden relative">
      {/* 3D Hyperspeed Background */}
      <div className="pointer-events-none fixed inset-0 z-0">
        <Hyperspeed effectOptions={hyperspeedOptions} />
      </div>

      {/* Ambient overlay to ensure text readability */}
      <div className="pointer-events-none fixed inset-0 z-0 bg-gradient-to-b from-black/80 via-transparent to-black/90" />

      {/* Topbar */}
      <header className="relative z-50 flex items-center justify-between px-6 sm:px-12 py-5 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <img src="/logo.svg" alt="JetWatch Logo" className="h-14 sm:h-16 w-auto" />
        </div>
        <div className="flex flex-col items-end">
          <div className="text-xs uppercase tracking-widest text-gray-400 font-bold mb-1 mr-2">Utilisateurs inscrits</div>
          {userCount > 0 ? (
            <Counter
              value={userCount}
              fontSize={48}
              padding={5}
              gap={6}
              textColor="white"
              fontWeight={900}
              gradientFrom="transparent"
            />
          ) : (
            <span className="text-4xl font-black text-white/40 tabular-nums">—</span>
          )}
        </div>
      </header>

      {/* Hero */}
      <main className="relative z-10 flex flex-col items-center justify-center text-center px-6 pt-6 pb-16">
        
        {/* Animated Badge / Logo */}
        <div className="w-48 h-48 md:w-64 md:h-64 mb-6 animate-fade-in relative z-20 flex items-center justify-center">
          <MetallicPaint
            imageSrc={logoBlack}
            seed={42}
            scale={4}
            patternSharpness={1}
            noiseScale={0.5}
            speed={0.3}
            liquid={0.75}
            mouseAnimation={true}
            brightness={2}
            contrast={0.5}
            refraction={0.01}
            blur={0.015}
            chromaticSpread={2}
            fresnel={1}
            angle={0}
            waveAmplitude={1}
            distortion={1}
            contour={0.2}
            lightColor="#ffffff"
            darkColor="#000000"
            tintColor="#e63946"
          />
        </div>

        {/* Title */}
        <h1 className="text-5xl sm:text-7xl md:text-8xl font-black tracking-tight leading-[0.95] mb-6">
          <ShinyText
            text="JETWATCH"
            speed={3}
            color="#ffffff"
            shineColor="#10b981"
            spread={120}
            className="block"
          />
          <ShinyText
            text="AFRIQUE"
            speed={3}
            delay={1.5}
            color="#10b981"
            shineColor="#34d399"
            spread={120}
            className="block"
          />
        </h1>

        {/* Subtitle */}
        <p className="text-xl sm:text-2xl font-semibold text-white/90 mb-4">
          <ShinyText
            text="Transparence des jets présidentiels africains"
            speed={4}
            color="#e5e5e5"
            shineColor="#ffffff"
            className="drop-shadow-sm"
          />
        </p>
        <p className="text-base sm:text-lg text-gray-300 max-w-lg mb-10 leading-relaxed font-medium">
          Des données en temps réel pour une gouvernance plus ouverte et responsable.
          Connectez-vous pour accéder au tableau de bord complet.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row items-center gap-4 mb-16">
          <button
            onClick={onLogin}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-3 px-8 py-4 bg-[#10b981] hover:bg-[#059669] text-white font-bold rounded-xl transition-all shadow-lg shadow-[#10b981]/20 hover:shadow-[#10b981]/30 hover:-translate-y-0.5 text-base"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            Se connecter pour accéder <ArrowRight className="w-4 h-4" />
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-8 sm:gap-16 mb-20">
          <div className="text-center">
            <div className="text-3xl sm:text-4xl font-black text-white tabular-nums">{animatedCount}</div>
            <div className="text-xs sm:text-sm text-gray-500 mt-1 uppercase tracking-wider">États surveillés</div>
          </div>
          <div className="text-center">
            <div className="text-3xl sm:text-4xl font-black text-[#10b981]">24/7</div>
            <div className="text-xs sm:text-sm text-gray-500 mt-1 uppercase tracking-wider">Surveillance</div>
          </div>
          <div className="text-center">
            <div className="text-3xl sm:text-4xl font-black text-white">OSINT</div>
            <div className="text-xs sm:text-sm text-gray-500 mt-1 uppercase tracking-wider">Intelligence</div>
          </div>
        </div>

        {/* Feature cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-4xl w-full">
          <div className="group relative p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06] hover:border-[#10b981]/30 transition-all hover:bg-white/[0.04]">
            <div className="w-14 h-14 rounded-2xl mb-4 overflow-hidden border border-[#10b981]/30 relative shadow-[0_0_15px_rgba(16,185,129,0.15)] group-hover:shadow-[0_0_25px_rgba(16,185,129,0.3)] transition-all duration-300">
              {/* Filtre de couleur vert pour correspondre à la palette */}
              <div className="absolute inset-0 bg-[#10b981] mix-blend-color z-10 pointer-events-none opacity-80"></div>
              {/* Voile sombre pour mieux s'intégrer au thème dark */}
              <div className="absolute inset-0 bg-black/20 z-10 pointer-events-none"></div>
              <img 
                src="/suivi-temps-reel-icon.svg" 
                alt="Suivi en temps réel" 
                className="w-full h-full object-cover scale-110 group-hover:scale-125 transition-transform duration-500"
              />
            </div>
            <h3 className="text-sm font-bold mb-2 text-[#10b981]">Suivi en temps réel</h3>
            <p className="text-xs text-gray-400 leading-relaxed">Trajectoires ADS-B et données OpenSky en continu sur tout le continent africain.</p>
          </div>
          
          <div className="group relative p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06] hover:border-[#3b82f6]/30 transition-all hover:bg-white/[0.04]">
            <div className="w-14 h-14 rounded-2xl mb-4 overflow-hidden border border-[#3b82f6]/30 relative shadow-[0_0_15px_rgba(59,130,246,0.15)] group-hover:shadow-[0_0_25px_rgba(59,130,246,0.3)] transition-all duration-300">
              {/* Filtre de couleur bleu pour correspondre à la palette */}
              <div className="absolute inset-0 bg-[#3b82f6] mix-blend-color z-10 pointer-events-none opacity-80"></div>
              {/* Voile sombre pour mieux s'intégrer au thème dark */}
              <div className="absolute inset-0 bg-black/20 z-10 pointer-events-none"></div>
              <img 
                src="/analyse-ia-icon.svg" 
                alt="Analyse IA" 
                className="w-full h-full object-cover scale-110 group-hover:scale-125 transition-transform duration-500"
              />
            </div>
            <h3 className="text-sm font-bold mb-2 text-[#3b82f6]">Analyse IA</h3>
            <p className="text-xs text-gray-400 leading-relaxed">Classification automatique des vols et scoring de transparence par intelligence artificielle.</p>
          </div>
          
          <div className="group relative p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06] hover:border-[#ef4444]/30 transition-all hover:bg-white/[0.04]">
            <div className="w-14 h-14 rounded-2xl mb-4 overflow-hidden border border-[#ef4444]/30 relative shadow-[0_0_15px_rgba(239,68,68,0.15)] group-hover:shadow-[0_0_25px_rgba(239,68,68,0.3)] transition-all duration-300">
              {/* Filtre de couleur rouge pour correspondre à la palette */}
              <div className="absolute inset-0 bg-[#ef4444] mix-blend-color z-10 pointer-events-none opacity-80"></div>
              {/* Voile sombre pour mieux s'intégrer au thème dark */}
              <div className="absolute inset-0 bg-black/20 z-10 pointer-events-none"></div>
              <img 
                src="/securite-ecc-icon.svg" 
                alt="Sécurité ECC" 
                className="w-full h-full object-cover scale-110 group-hover:scale-125 transition-transform duration-500"
              />
            </div>
            <h3 className="text-sm font-bold mb-2 text-[#ef4444]">Sécurité ECC</h3>
            <p className="text-xs text-gray-400 leading-relaxed">Authentification par courbe elliptique et tokens JWT ES256 pour une sécurité maximale.</p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/[0.06] py-6 text-center">
        <p className="text-xs text-gray-600">
          © 2026 JetWatch Afrique — Plateforme de transparence &bull; Données OpenSky Network
        </p>
      </footer>

      <style>{`
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fade-in 0.8s ease-out;
        }
      `}</style>
    </div>
  );
}
