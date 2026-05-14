import React, { useState, useEffect, useRef } from 'react';
import styled from 'styled-components';
import { Play, Pause, X, MonitorPlay, Music, Volume2 } from 'lucide-react';
import GlassSurface from './GlassSurface';
import ElasticSlider from './ElasticSlider';

// Playlist de démonstration avec musiques libres de droits
const PLAYLIST = [
  { id: 1, name: "Skyfall", artist: "Adele", src: "/music/Adele_-_Skyfall__Official_Lyric_Video_(256k).mp3", cover: "bg-blue-900" },
  { id: 2, name: "I Wanna Be Yours", artist: "Arctic Monkeys", src: "/music/Arctic_Monkeys_-_I_Wanna_Be_Yours(256k).mp3", cover: "bg-red-800" },
  { id: 3, name: "thank u, next", artist: "Ariana Grande", src: "/music/Ariana_Grande_-_thank_u,_next__Official_Lyric_Video_(140).m4a", cover: "bg-pink-400" },
  { id: 4, name: "CARO", artist: "Bad Bunny", src: "/music/BAD_BUNNY_-_CARO___X100PRE__Video_Oficial_(128k).mp3", cover: "bg-yellow-500" },
  { id: 5, name: "God's Plan", artist: "Drake", src: "/music/Drake_-_God_s_Plan(256k).mp3", cover: "bg-gray-800" },
  { id: 6, name: "Emotionally Scarred", artist: "Lil Baby", src: "/music/Lil_Baby_-_Emotionally_Scarred__Lyrics_(256k).mp3", cover: "bg-indigo-600" },
  { id: 7, name: "All My Life", artist: "Lil Durk ft. J. Cole", src: "/music/Lil_Durk_-_All_My_Life_ft._J._Cole(256k).mp3", cover: "bg-orange-600" },
  { id: 8, name: "Finesse Out The Gang Way", artist: "Lil Durk ft. Lil Baby", src: "/music/Lil_Durk_-_Finesse_Out_The_Gang_Way_feat._Lil_Baby__Official_Music_Video_(256k).mp3", cover: "bg-blue-600" },
  { id: 9, name: "Love me not", artist: "Ravyn Lenae", src: "/music/Love_me_not_-_Ravyn_Lenae__Sub_español_(256k).mp3", cover: "bg-rose-400" },
  { id: 10, name: "OUTRO", artist: "M83", src: "/music/M83_-_OUTRO__Lyrics_(256k).mp3", cover: "bg-purple-900" },
  { id: 11, name: "MAGIE", artist: "Maes", src: "/music/Maes_-_MAGIE__Clip_Officiel_(256k).mp3", cover: "bg-emerald-700" },
  { id: 12, name: "Earth Song", artist: "Michael Jackson", src: "/music/Michael_Jackson_-_Earth_Song__Official_Video_(256k).mp3", cover: "bg-green-800" },
  { id: 13, name: "You Rock My World", artist: "Michael Jackson", src: "/music/Michael_Jackson_-_You_Rock_My_World__Official_Video_-_Shortened_Version_(256k).mp3", cover: "bg-amber-600" },
  { id: 14, name: "Ballin'", artist: "Mustard ft. Roddy Ricch", src: "/music/Mustard_-_Ballin__Lyrics__Feat._Roddy_Ricch(256k).mp3", cover: "bg-blue-400" },
  { id: 15, name: "The Fate of Ophelia", artist: "Taylor Swift", src: "/music/Taylor_Swift_-_The_Fate_of_Ophelia__Official_Music_Video_(256k).mp3", cover: "bg-violet-700" },
  { id: 16, name: "The Prophecy", artist: "Taylor Swift", src: "/music/Taylor_Swift_-_The_Prophecy__Official_Lyric_Video_(256k).mp3", cover: "bg-stone-600" },
  { id: 17, name: "ABC", artist: "The Jacksons", src: "/music/The_Jackson_-_ABC__Lyrics_Video__🎤(256k).mp3", cover: "bg-red-500" },
  { id: 18, name: "Heartless", artist: "The Weeknd", src: "/music/The_Weeknd_-_Heartless__Lyrics_(256k).mp3", cover: "bg-red-900" },
  { id: 19, name: "Starboy", artist: "The Weeknd ft. Daft Punk", src: "/music/The_Weeknd_-_Starboy__Lyrics__ft._Daft_Punk(256k).mp3", cover: "bg-zinc-900" },
  { id: 20, name: "Shine", artist: "Unknown", src: "/music/shine .mp3", cover: "bg-cyan-500" },
];

const formatTime = (time: number) => {
  if (isNaN(time)) return "0:00";
  const minutes = Math.floor(time / 60);
  const seconds = Math.floor(time % 60);
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

export default function MusicPlayer({ 
  onClose, 
  audioRef, 
  onToggleScreensaver,
  isScreensaverActive
}: { 
  onClose: () => void, 
  audioRef: React.RefObject<HTMLAudioElement | null>,
  onToggleScreensaver: () => void,
  isScreensaverActive: boolean
}) {
  const [currentSongIndex, setCurrentSongIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(50);
  
  const currentSong = PLAYLIST[currentSongIndex];

  // Sync state with audio element
  useEffect(() => {
    if (!audioRef.current) return;
    const audio = audioRef.current;
    
    if (!audio.src || !audio.src.includes(currentSong.src)) {
        audio.src = currentSong.src;
    }

    const onTimeUpdate = () => {
      setProgress(audio.currentTime);
      setDuration(audio.duration);
    };
    const onEnded = () => {
      playNext();
    };

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('ended', onEnded);
    
    audio.volume = volume / 100;

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('ended', onEnded);
    };
  }, [currentSongIndex, volume, audioRef]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch(e => console.error("Playback failed:", e));
    }
    setIsPlaying(!isPlaying);
  };

  const playSong = (index: number) => {
    setCurrentSongIndex(index);
    setIsPlaying(true);
    if (audioRef.current) {
        audioRef.current.src = PLAYLIST[index].src;
        audioRef.current.play().catch(e => console.error(e));
    }
  };

  const playNext = () => {
    playSong((currentSongIndex + 1) % PLAYLIST.length);
  };

  return (
    <div className="absolute right-0 top-14 z-50 w-[320px] origin-top-right animate-in fade-in zoom-in-95 duration-300">
        <GlassSurface 
          width={320}
          height={550}
          borderRadius={24}
          className="shadow-2xl overflow-hidden border border-white/10"
          opacity={0.1}
          backgroundOpacity={0.4}
          blur={20}
        >
           <div className="flex flex-col h-full w-full">
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b border-white/5 bg-white/5">
                <div className="flex items-center gap-2">
                   <div className="w-8 h-8 rounded-full bg-[#1db954]/20 flex items-center justify-center">
                      <Music size={16} className="text-[#1db954]" />
                   </div>
                   <span className="font-bold text-sm tracking-tight text-white">JET RADIO</span>
                </div>
              </div>

              {/* Scrollable Playlist Container */}
              <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
                {PLAYLIST.map((song, i) => {
                  const isActive = currentSongIndex === i;
                  return (
                    <div 
                      key={song.id} 
                      className={`group flex items-center gap-3 p-2 rounded-xl transition-all cursor-pointer ${isActive ? 'bg-white/10' : 'hover:bg-white/5'}`}
                      onClick={() => playSong(i)}
                    >
                      <div className={`w-10 h-10 rounded-lg ${song.cover} flex-shrink-0 flex items-center justify-center overflow-hidden relative shadow-inner`}>
                         {isActive && isPlaying ? (
                            <div className="flex gap-0.5 items-end h-4">
                               <div className="w-1 bg-white animate-[playing_1s_ease-in-out_infinite_0.1s] rounded-full" />
                               <div className="w-1 bg-white animate-[playing_1s_ease-in-out_infinite_0.3s] rounded-full" />
                               <div className="w-1 bg-white animate-[playing_1s_ease-in-out_infinite_0.5s] rounded-full" />
                            </div>
                         ) : (
                            <Play size={14} className={`text-white transition-opacity ${isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} fill="currentColor" />
                         )}
                      </div>
                      <div className="flex-1 min-w-0">
                         <p className={`text-xs font-bold truncate ${isActive ? 'text-[#1db954]' : 'text-white/90'}`}>{song.name}</p>
                         <p className="text-[10px] text-white/40 truncate font-medium uppercase tracking-wider">{song.artist}</p>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Mini Player Control at bottom */}
              <div className="p-4 bg-black/40 border-t border-white/5 backdrop-blur-md">
                 <div className="flex items-center gap-4 mb-3">
                    <div className={`w-12 h-12 rounded-xl ${currentSong.cover} shadow-lg shadow-black/40 flex-shrink-0`} />
                    <div className="flex-1 min-w-0">
                       <p className="text-sm font-bold truncate text-white">{currentSong.name}</p>
                       <p className="text-xs text-white/50 truncate">{currentSong.artist}</p>
                    </div>
                 </div>

                 {/* Progress Bar */}
                 <div className="relative h-1 w-full bg-white/10 rounded-full overflow-hidden mb-4 group cursor-pointer">
                    <div 
                       className="absolute top-0 left-0 h-full bg-[#1db954] transition-all duration-100" 
                       style={{ width: `${duration ? (progress / duration) * 100 : 0}%` }}
                    />
                 </div>

                 <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                       <button onClick={togglePlay} className="w-10 h-10 rounded-full bg-white text-black flex items-center justify-center hover:scale-105 active:scale-95 transition-transform flex-shrink-0">
                          {isPlaying ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" className="ml-0.5" />}
                       </button>
                       
                       <div className="flex items-center gap-2 group/vol">
                          <Volume2 size={14} className="text-white/40 group-hover/vol:text-white transition-colors" />
                          <div className="w-20">
                             <ElasticSlider
                                startingValue={0}
                                defaultValue={volume}
                                maxValue={100}
                                isStepped={false}
                                leftIcon={<></>}
                                rightIcon={<></>}
                                onChange={(val: number) => setVolume(val)}
                              />
                          </div>
                       </div>
                    </div>

                    <button 
                       onClick={onToggleScreensaver}
                       className={`p-2 rounded-lg transition-colors ${isScreensaverActive ? 'bg-[#1db954] text-black shadow-glow-green' : 'text-white/40 hover:text-white hover:bg-white/10'}`}
                       title="Mode Immersion"
                    >
                       <MonitorPlay size={20} />
                    </button>
                 </div>
              </div>
           </div>
        </GlassSurface>

        <style dangerouslySetInnerHTML={{ __html: `
          .custom-scrollbar::-webkit-scrollbar {
            width: 4px;
          }
          .custom-scrollbar::-webkit-scrollbar-track {
            background: transparent;
          }
          .custom-scrollbar::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
          }
          .custom-scrollbar::-webkit-scrollbar-thumb:hover {
            background: rgba(255,255,255,0.1);
          }
          @keyframes playing {
            0%, 100% { height: 4px; }
            50% { height: 16px; }
          }
        `}} />
    </div>
  );
}
