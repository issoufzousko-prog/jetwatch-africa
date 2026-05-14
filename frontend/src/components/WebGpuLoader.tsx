import React from 'react';

interface LoaderProps {
  progress: number; // 0 to 100
  text?: string;
}

const WebGpuLoader: React.FC<LoaderProps> = ({ progress, text = "Chargement de l'IA" }) => {
  // Ensure progress is between 0 and 100, then format it
  const safeProgress = Math.min(Math.max(progress, 0), 100);
  const displayProgress = safeProgress.toFixed(1);

  return (
    <div className="flex flex-col items-center gap-2 p-5 font-sans">
      <div className="text-white text-lg font-semibold tracking-wide animate-pulse">
        {text} <span className="text-accent-blue">{displayProgress}%</span>
        <span className="dot animate-bounce inline-block ml-1">.</span>
        <span className="dot animate-bounce inline-block ml-1" style={{ animationDelay: '0.2s' }}>.</span>
        <span className="dot animate-bounce inline-block ml-1" style={{ animationDelay: '0.4s' }}>.</span>
      </div>
      
      <div className="relative w-48 h-8 rounded-full overflow-hidden shadow-inner" style={{ background: 'linear-gradient(135deg, #2a2a2a, #1a1a1a)' }}>
        <div 
          className="absolute top-0.5 left-0.5 h-[calc(100%-4px)] rounded-full transition-all duration-300 ease-out shadow-lg"
          style={{
            width: `calc(${safeProgress}% - 4px)`,
            minWidth: '4px',
            background: 'linear-gradient(90deg, #4f46e5, #7c3aed, #ec4899, #f59e0b)',
            animation: 'colorShift 3s linear infinite'
          }}
        />
      </div>

      <style>{`
        @keyframes colorShift {
          0% { filter: hue-rotate(0deg) brightness(1); }
          33% { filter: hue-rotate(120deg) brightness(1.1); }
          66% { filter: hue-rotate(240deg) brightness(0.9); }
          100% { filter: hue-rotate(360deg) brightness(1); }
        }
      `}</style>
    </div>
  );
};

export default WebGpuLoader;
