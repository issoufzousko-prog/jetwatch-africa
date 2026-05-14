import React from 'react';
import Antigravity from './Antigravity';

interface ScreensaverProps {
  frequencies: { bass: number, mid: number, treble: number, overall: number };
  onClose: () => void;
}

export default function Screensaver({ frequencies, onClose }: ScreensaverProps) {
  // Map audio frequencies to visual parameters
  
  // waveAmplitude: 0 to 3 based on bass
  const waveAmplitude = 0.5 + (frequencies.bass * 2.5);
  
  // particleSize: 1 to 4 based on overall volume
  const particleSize = 1 + (frequencies.overall * 3);
  
  // pulseSpeed: 1 to 8 based on treble
  const pulseSpeed = 1 + (frequencies.treble * 7);

  // Dynamic color based on frequencies
  const r = Math.floor(Math.min(255, 50 + frequencies.bass * 205));
  const g = Math.floor(Math.min(255, 50 + frequencies.mid * 205));
  const b = Math.floor(Math.min(255, 100 + frequencies.treble * 155));
  
  // Convert RGB to HEX
  const toHex = (n: number) => n.toString(16).padStart(2, '0');
  const color = `#${toHex(r)}${toHex(g)}${toHex(b)}`;

  return (
    <div 
      className="fixed inset-0 z-[100] bg-black/90 cursor-pointer overflow-hidden backdrop-blur-sm"
      onClick={onClose}
      title="Cliquez n'importe où pour quitter le mode veille"
    >
      {/* Instructions */}
      <div className="absolute top-10 w-full text-center text-white/50 text-sm z-[101] pointer-events-none">
        Cliquez pour quitter le mode veille
      </div>

      <div className="w-full h-full relative flex items-center justify-center">
        <Antigravity
          count={300}
          magnetRadius={6}
          ringRadius={7}
          waveSpeed={0.4}
          waveAmplitude={waveAmplitude}
          particleSize={particleSize}
          lerpSpeed={0.05}
          color={color}
          autoAnimate
          particleVariance={1}
          rotationSpeed={0.5} // slight rotation for dynamism
          depthFactor={1}
          pulseSpeed={pulseSpeed}
          particleShape="capsule"
          fieldStrength={10}
        />
      </div>
    </div>
  );
}
