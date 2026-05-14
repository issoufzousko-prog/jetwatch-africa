import { useState, useEffect, useRef } from 'react';

export function useAudioVisualizer(audioElement: HTMLAudioElement | null) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [frequencies, setFrequencies] = useState({ bass: 0, mid: 0, treble: 0, overall: 0 });
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const animationFrameRef = useRef<number>(0);

  useEffect(() => {
    if (!audioElement) return;

    const setupAudio = () => {
      // Create context only once per audio element, after user interaction
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        analyserRef.current = audioContextRef.current.createAnalyser();
        analyserRef.current.fftSize = 256;
        sourceRef.current = audioContextRef.current.createMediaElementSource(audioElement);
        sourceRef.current.connect(analyserRef.current);
        analyserRef.current.connect(audioContextRef.current.destination);
      }
    };

    const handlePlay = () => {
      setupAudio();
      if (audioContextRef.current?.state === 'suspended') {
        audioContextRef.current.resume();
      }
      setIsPlaying(true);
      updateFrequencies();
    };

    const handlePause = () => {
      setIsPlaying(false);
      cancelAnimationFrame(animationFrameRef.current);
    };

    audioElement.addEventListener('play', handlePlay);
    audioElement.addEventListener('pause', handlePause);

    return () => {
      audioElement.removeEventListener('play', handlePlay);
      audioElement.removeEventListener('pause', handlePause);
      cancelAnimationFrame(animationFrameRef.current);
    };
  }, [audioElement]);

  const updateFrequencies = () => {
    if (!analyserRef.current || !isPlaying) return;

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);

    // Calculate averages for different frequency bands
    let bassSum = 0, midSum = 0, trebleSum = 0, overallSum = 0;
    const third = Math.floor(dataArray.length / 3);

    for (let i = 0; i < dataArray.length; i++) {
      overallSum += dataArray[i];
      if (i < third) bassSum += dataArray[i];
      else if (i < third * 2) midSum += dataArray[i];
      else trebleSum += dataArray[i];
    }

    setFrequencies({
      bass: (bassSum / third) / 255, // Normalized 0-1
      mid: (midSum / third) / 255,
      treble: (trebleSum / (dataArray.length - third * 2)) / 255,
      overall: (overallSum / dataArray.length) / 255,
    });

    animationFrameRef.current = requestAnimationFrame(updateFrequencies);
  };

  return { isPlaying, frequencies };
}
