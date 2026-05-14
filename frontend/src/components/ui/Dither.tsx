import { useEffect, useRef } from 'react';

interface DitherProps {
  waveColor?: [number, number, number];
  disableAnimation?: boolean;
  enableMouseInteraction?: boolean;
  mouseRadius?: number;
  colorNum?: number;
  waveAmplitude?: number;
  waveFrequency?: number;
  waveSpeed?: number;
}

export default function Dither({
  waveColor = [0.1, 0.4, 0.8], // Default to an accent blue tint
  disableAnimation = false,
  enableMouseInteraction = true,
  mouseRadius = 0.3,
  colorNum = 4,
  waveAmplitude = 0.3,
  waveFrequency = 3,
  waveSpeed = 0.05,
}: DitherProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let time = 0;
    
    // Resize handler
    const resize = () => {
      canvas.width = canvas.parentElement?.clientWidth || window.innerWidth;
      canvas.height = canvas.parentElement?.clientHeight || window.innerHeight;
    };
    window.addEventListener('resize', resize);
    resize();

    // Mouse state
    let mouseX = -1000;
    let mouseY = -1000;
    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseX = e.clientX - rect.left;
      mouseY = e.clientY - rect.top;
    };
    if (enableMouseInteraction) {
      window.addEventListener('mousemove', handleMouseMove);
    }

    const ditherMatrix = [
      [0, 8, 2, 10],
      [12, 4, 14, 6],
      [3, 11, 1, 9],
      [15, 7, 13, 5]
    ];

    const render = () => {
      time += waveSpeed;
      const w = canvas.width;
      const h = canvas.height;
      const imageData = ctx.createImageData(w, h);
      const data = imageData.data;

      // Base matrix for noise/dither
      for (let y = 0; y < h; y += 4) {
        for (let x = 0; x < w; x += 4) {
          
          // Calculate wave based on position and time
          const nx = x / w;
          const ny = y / h;
          
          // Add some noise
          let val = Math.sin(nx * waveFrequency * Math.PI * 2 + time) * 
                    Math.cos(ny * waveFrequency * Math.PI * 2 + time) * waveAmplitude;
          
          // Mouse interaction (repel)
          if (enableMouseInteraction) {
            const dx = (x - mouseX) / w;
            const dy = (y - mouseY) / h;
            const dist = Math.sqrt(dx*dx + dy*dy);
            if (dist < mouseRadius) {
              val += (1 - dist / mouseRadius) * 0.5;
            }
          }

          // Normalize val to 0-1
          val = (val + 1) / 2;
          val = Math.max(0, Math.min(1, val));

          // Draw a 4x4 block
          for (let dy = 0; dy < 4; dy++) {
            if (y + dy >= h) continue;
            for (let dx = 0; dx < 4; dx++) {
              if (x + dx >= w) continue;
              
              const threshold = (ditherMatrix[dy][dx] + 0.5) / 16;
              const outputVal = val > threshold ? 1 : 0;
              
              const index = ((y + dy) * w + (x + dx)) * 4;
              
              // Apply color tint and opacity
              const r = Math.floor(waveColor[0] * 255);
              const g = Math.floor(waveColor[1] * 255);
              const b = Math.floor(waveColor[2] * 255);
              
              // Dark background (0,0,0) or tinted points
              data[index] = outputVal * r;     // R
              data[index+1] = outputVal * g;   // G
              data[index+2] = outputVal * b;   // B
              data[index+3] = outputVal ? 255 : 20; // Alpha
            }
          }
        }
      }
      
      ctx.putImageData(imageData, 0, 0);

      if (!disableAnimation) {
        animationFrameId = requestAnimationFrame(render);
      }
    };

    render();

    return () => {
      window.removeEventListener('resize', resize);
      if (enableMouseInteraction) {
        window.removeEventListener('mousemove', handleMouseMove);
      }
      cancelAnimationFrame(animationFrameId);
    };
  }, [waveColor, disableAnimation, enableMouseInteraction, mouseRadius, colorNum, waveAmplitude, waveFrequency, waveSpeed]);

  return (
    <canvas 
      ref={canvasRef} 
      className="absolute inset-0 w-full h-full opacity-30 mix-blend-screen pointer-events-none"
    />
  );
}
