import { useState, useEffect, useRef } from 'react';
import { Plane, LogOut, Music } from 'lucide-react';
import type { TabType, AuthUser } from '../App';
import AvatarCircles from './AvatarCircles';
import MusicPlayer from './MusicPlayer';
import Screensaver from './Screensaver';
import { useAudioVisualizer } from '../hooks/useAudioVisualizer';

interface TopbarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  currentUser: AuthUser | null;
  onLogout: () => void;
}

const navItems = [
  { id: 'dashboard', label: 'Tableau de bord' },
  { id: 'ranking', label: 'Classement' },
  { id: 'live', label: 'Carte en direct' }
] as const;

export default function Topbar({ activeTab, setActiveTab, currentUser, onLogout }: TopbarProps) {
  const [users, setUsers] = useState<any[]>([]);
  const [isMusicPlayerOpen, setIsMusicPlayerOpen] = useState(false);
  const [isScreensaverActive, setIsScreensaverActive] = useState(false);
  
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const { isPlaying, frequencies } = useAudioVisualizer(audioRef.current);

  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || '';
    
    // Fetch public users
    fetch(`${apiUrl}/api/users`)
      .then(res => res.json())
      .then(data => { if (Array.isArray(data)) setUsers(data); })
      .catch(console.error);
  }, []);
  
  const avatars = users.length > 0 
    ? users.slice(0, 10).map(u => ({ imageUrl: u.avatar_url, profileUrl: `#` }))
    : [];

  return (
    <>
      <header className="px-md sm:px-xl lg:px-2xl pt-md w-full border-b border-border-subtle bg-background/50 backdrop-blur-md pb-md sticky top-0 z-50">
        {/* Global Audio Element */}
        <audio ref={audioRef} crossOrigin="anonymous" />
        
        <div className="flex flex-col gap-sm sm:gap-lg max-w-[1440px] mx-auto w-full">
          
          {/* Row 1: Logo | Nav Pills (center) | Actions */}
          <div className="relative flex items-center justify-between">
            {/* Logo */}
            <button onClick={() => setActiveTab('dashboard')} className="flex items-center gap-sm">
              <img src="/logo.svg" alt="JetWatch Logo" className="h-10 sm:h-12 w-auto" />
            </button>
            
            {/* Nav centrale — position ABSOLUTE centrée */}
            <nav className="hidden lg:flex items-center gap-3xs bg-white/[0.04] dark:bg-white/[0.04] rounded-full px-2xs py-2xs absolute left-1/2 -translate-x-1/2 border border-border-subtle">
              {navItems.map(item => {
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id as TabType)}
                    className={`px-lg py-xs rounded-full sp-label transition-all ${
                      isActive
                        ? 'bg-foreground text-background shadow-sm'
                        : 'text-muted-foreground hover:text-foreground hover:bg-white/[0.04] dark:hover:bg-white/[0.06]'
                    }`}
                  >
                    {item.label}
                  </button>
                );
              })}
            </nav>
            
            {/* Actions droite */}
            <div className="flex items-center gap-md relative">
              <div className="hidden sm:block">
                {avatars.length > 0 && <AvatarCircles avatarUrls={avatars} numPeople={Math.max(0, users.length - avatars.length)} className="scale-90 origin-right" />}
              </div>
              
              {/* Music Player Toggle */}
              <button 
                onClick={() => setIsMusicPlayerOpen(!isMusicPlayerOpen)}
                className={`relative p-xs rounded-full transition-colors ${isMusicPlayerOpen || isPlaying ? 'text-[#1db954] bg-[#1db954]/10' : 'text-muted-foreground hover:text-foreground'}`}
                title="Lecteur de Musique"
              >
                <Music className="w-5 h-5" />
                {isPlaying && (
                  <span className="absolute top-0 right-0 w-2 h-2 rounded-full bg-[#1db954] animate-pulse" />
                )}
              </button>

              {/* Music Player Popover */}
              {isMusicPlayerOpen && (
                 <MusicPlayer 
                    onClose={() => setIsMusicPlayerOpen(false)} 
                    audioRef={audioRef}
                    onToggleScreensaver={() => setIsScreensaverActive(!isScreensaverActive)}
                    isScreensaverActive={isScreensaverActive}
                 />
              )}

              {currentUser && (
                 <div className="flex items-center gap-2 ml-2 border-l border-glass-border pl-4">
                    <img src={currentUser.avatar_url || "https://ui-avatars.com/api/?name=U"} alt="Profile" className="w-8 h-8 rounded-full border border-glass-border" referrerPolicy="no-referrer" />
                    <span className="sp-caption text-muted-foreground hidden md:inline">{currentUser.name}</span>
                    <button onClick={onLogout} className="p-xs rounded-full text-muted-foreground hover:text-accent-red transition-colors" title="Se déconnecter">
                      <LogOut className="w-4 h-4" />
                    </button>
                 </div>
              )}
            </div>
          </div>

          {/* Row 2: Titre + Subtitle */}
          <div className="flex flex-col sm:flex-row sm:items-end gap-sm mt-xs">
            <div className="flex-1 min-w-0">
              <h1 className="sp-h3 sm:sp-h2 text-foreground font-black">JETWATCH AFRIQUE</h1>
              <p className="sp-caption sm:sp-body text-muted-foreground mt-3xs hidden sm:block">
                Transparence des jets presidentiels africains &bull; En temps reel
              </p>
            </div>
          </div>
          
        </div>
      </header>

      {/* Screensaver Fullscreen Overlay */}
      {isScreensaverActive && (
        <Screensaver 
          frequencies={frequencies} 
          onClose={() => setIsScreensaverActive(false)} 
        />
      )}
    </>
  );
}
