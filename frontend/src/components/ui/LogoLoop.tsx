import { useRef, useEffect } from 'react';

interface LogoItem {
  node?: React.ReactNode;
  src?: string;
  alt?: string;
  title: string;
  href?: string;
}

interface LogoLoopProps {
  logos: LogoItem[];
  speed?: number;       // px/s
  logoHeight?: number;
  gap?: number;
  direction?: 'left' | 'right';
  fadeOut?: boolean;
}

export default function LogoLoop({
  logos,
  speed = 80,
  logoHeight = 40,
  gap = 48,
  direction = 'left',
  fadeOut = true,
}: LogoLoopProps) {
  const trackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;

    let startTime: number | null = null;
    let animId: number;
    const totalWidth = track.scrollWidth / 2; // deux copies

    const animate = (ts: number) => {
      if (!startTime) startTime = ts;
      const elapsed = (ts - startTime) / 1000;
      let offset = (elapsed * speed) % totalWidth;
      if (direction === 'right') offset = -offset;
      track.style.transform = `translateX(-${offset}px)`;
      animId = requestAnimationFrame(animate);
    };

    animId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animId);
  }, [speed, direction]);

  const items = [...logos, ...logos]; // double pour le seamless loop

  return (
    <div
      className="relative overflow-hidden w-full"
      style={{
        maskImage: fadeOut
          ? 'linear-gradient(to right, transparent 0%, black 10%, black 90%, transparent 100%)'
          : undefined,
        WebkitMaskImage: fadeOut
          ? 'linear-gradient(to right, transparent 0%, black 10%, black 90%, transparent 100%)'
          : undefined,
      }}
    >
      <div
        ref={trackRef}
        className="flex will-change-transform"
        style={{ gap: `${gap}px`, width: 'max-content' }}
      >
        {items.map((logo, i) => (
          <div
            key={i}
            className="flex flex-col items-center justify-center shrink-0 select-none"
            style={{ height: logoHeight, minWidth: logoHeight }}
            title={logo.title}
          >
            {logo.src ? (
              <img
                src={logo.src}
                alt={logo.alt || logo.title}
                style={{ height: logoHeight, width: 'auto', objectFit: 'contain' }}
                draggable={false}
              />
            ) : (
              <div
                className="flex items-center justify-center text-slate-300 opacity-70 hover:opacity-100 transition-opacity"
                style={{ fontSize: logoHeight * 0.7 }}
              >
                {logo.node}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
