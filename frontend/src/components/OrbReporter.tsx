import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { ReportSection } from '../hooks/useWebLLM';

interface OrbReporterProps {
  sections: ReportSection[];
  onComplete: () => void;
}

export const OrbReporter = ({ sections, onComplete }: OrbReporterProps) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [pulse, setPulse] = useState(1);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Gérer la lecture audio séquentielle
  useEffect(() => {
    if (sections.length === 0 || currentIndex >= sections.length) return;

    const currentSection = sections[currentIndex];
    
    // Si on n'a pas encore créé l'élément audio pour cette section
    if (audioRef.current) {
      audioRef.current.pause();
    }
    
    const apiUrl = import.meta.env.VITE_API_URL || '';
    const audioUrl = `${apiUrl}/api/tts?text=${encodeURIComponent(currentSection.text)}`;
    const audio = new Audio(audioUrl);
    audioRef.current = audio;
    
    setIsPlaying(true);
    
    // Animation du pulse pendant la lecture (simulé car pas d'accès WebAudio Analyzer facile sur stream)
    const pulseInterval = setInterval(() => {
      setPulse(Math.random() * 0.1 + 1); // pulse entre 1.0 et 1.1
    }, 200);

    audio.onended = () => {
      clearInterval(pulseInterval);
      setPulse(1);
      setIsPlaying(false);
      
      if (currentIndex < sections.length - 1) {
        // Passer à la section suivante
        setCurrentIndex(prev => prev + 1);
      } else {
        // Fin de la présentation
        onComplete();
      }
    };

    audio.onerror = () => {
      console.error("Erreur lecture audio");
      clearInterval(pulseInterval);
      setPulse(1);
      setIsPlaying(false);
      // Passer quand même à la suite pour ne pas bloquer
      if (currentIndex < sections.length - 1) {
        setCurrentIndex(prev => prev + 1);
      } else {
        onComplete();
      }
    };

    // Jouer
    audio.play().catch(e => {
      console.error("Audio play prevented:", e);
      // Auto-play block : essayer de jouer muté ou ignorer
    });

    return () => {
      clearInterval(pulseInterval);
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, [currentIndex, sections, onComplete]);

  if (sections.length === 0) return null;

  const currentSection = sections[currentIndex];

  return (
    <div className="relative w-full h-full flex items-center justify-center bg-black overflow-hidden rounded-xl border border-white/5">
      {/* BACKGROUND: Orb CSS */}
      <motion.div
        className="absolute inset-0 flex items-center justify-center pointer-events-none"
        animate={{ scale: pulse }}
        transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      >
        <div 
          className="w-[800px] h-[800px] rounded-full opacity-30"
          style={{
            background: 'radial-gradient(circle, rgba(139,92,246,0.8) 0%, rgba(88,28,135,0.4) 30%, rgba(0,0,0,0) 70%)',
            filter: 'blur(60px)'
          }}
        />
      </motion.div>

      {/* MIDDLE LAYER: Slides */}
      <div className="z-10 w-full max-w-5xl px-8 h-full flex flex-col justify-center">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentIndex}
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 1.05 }}
            transition={{ duration: 0.8, ease: "easeInOut" }}
            className="flex flex-row gap-12 items-center"
          >
            {/* Image Section */}
            {currentSection.imageUrl && (
              <div className="w-1/2 flex-shrink-0">
                <div className="relative rounded-2xl overflow-hidden shadow-[0_0_50px_rgba(139,92,246,0.3)] border border-purple-500/30">
                  <img 
                    src={currentSection.imageUrl} 
                    alt="Investigation Evidence" 
                    className="w-full h-[400px] object-cover"
                  />
                  <div className="absolute inset-0 border-2 border-white/10 rounded-2xl pointer-events-none mix-blend-overlay"></div>
                </div>
              </div>
            )}

            {/* Text Section */}
            <div className={`flex flex-col gap-6 ${currentSection.imageUrl ? 'w-1/2' : 'w-full text-center items-center'}`}>
              <h2 className="text-4xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-indigo-400">
                {currentSection.title}
              </h2>
              
              <p className="text-xl leading-relaxed text-slate-300 font-medium">
                {currentSection.text}
              </p>

              {currentSection.sourceName && (
                <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-900/30 border border-purple-500/20 w-fit">
                  <span className="text-purple-400 text-sm">Source confirmée :</span>
                  <span className="text-white font-mono text-sm">{currentSection.sourceName}</span>
                </div>
              )}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* AUDIO INDICATOR */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex gap-1 items-center">
        <div className="text-xs text-purple-400/50 uppercase tracking-widest mr-4 font-mono">
          Phase {currentIndex + 1} / {sections.length}
        </div>
        {[...Array(5)].map((_, i) => (
          <motion.div
            key={i}
            className="w-1 bg-purple-500 rounded-full"
            animate={{ height: isPlaying ? [10, 20 + Math.random() * 20, 10] : 4 }}
            transition={{ repeat: Infinity, duration: 0.5 + i * 0.1 }}
          />
        ))}
      </div>
    </div>
  );
};
