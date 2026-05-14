import { useState, useEffect } from 'react';
import { Toaster } from 'sonner';
import Topbar from './components/Topbar';
import Sidebar from './components/Sidebar';
import Dashboard from './views/Dashboard';
import RankingPage from './views/RankingPage';
import LivePage from './views/LivePage';
import ShareView from './views/ShareView';
import ErrorBoundary from './components/ErrorBoundary';
import LandingPage from './views/LandingPage';
import { initSecurity } from './services/api';

export type TabType = 'dashboard' | 'ranking' | 'live';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  avatar_url: string;
  provider: string;
  role: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [selectedCountry, setSelectedCountry] = useState<string | null>("Nigeria");
  const [isShareView, setIsShareView] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    // Initialiser le système de sécurité EC-PoW + ECDH au démarrage
    // Le handshake ECDH et le premier challenge PoW sont résolus silencieusement
    initSecurity().catch(err => console.warn('[Security] Init échoué:', err));
  }, []);

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    if (searchParams.get('view') === 'share') {
      setIsShareView(true);
    }
  }, []);

  // Centralized auth check
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || '';
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    
    if (token) {
      localStorage.setItem('auth_token', token);
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    const savedToken = localStorage.getItem('auth_token');
    if (savedToken) {
      import('./services/api').then(({ api }) => {
        api.getCurrentUser()
        .then(data => {
          setCurrentUser(data);
          setAuthLoading(false);
        })
        .catch(() => {
          localStorage.removeItem('auth_token');
          setCurrentUser(null);
          setAuthLoading(false);
        });
      });
    } else {
      setAuthLoading(false);
    }
  }, []);

  const handleLogin = () => {
    const apiUrl = import.meta.env.VITE_API_URL || '';
    window.location.href = `${apiUrl}/api/auth/login/google`;
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    setCurrentUser(null);
  };

  if (isShareView) {
    return <ShareView />;
  }

  // Show landing page if not authenticated
  if (!authLoading && !currentUser) {
    return <LandingPage onLogin={handleLogin} />;
  }

  // Show loading while checking auth
  if (authLoading) {
    return (
      <div className="dark flex min-h-svh items-center justify-center bg-background text-foreground">
        <div className="flex flex-col items-center gap-4">
          <div className="size-10 rounded-full border-2 border-accent-green border-t-transparent animate-spin" />
          <p className="sp-caption text-muted-foreground animate-pulse">Vérification de l'authentification...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dark flex min-h-svh flex-col bg-background text-foreground">
      <Toaster
        position="bottom-right"
        theme="dark"
        richColors
        toastOptions={{
          style: { background: '#0f172a', border: '1px solid rgba(255,255,255,0.08)', color: '#f8fafc' },
        }}
      />
      <Topbar activeTab={activeTab} setActiveTab={setActiveTab} currentUser={currentUser} onLogout={handleLogout} />
      
      <main className="relative flex-1 p-md sm:p-xl lg:p-2xl">
        {/* Glow décoratif style ShopPulse */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden dark:block hidden">
          <div className="absolute -top-[300px] -right-[200px] size-[700px] rounded-full bg-primary/[0.03] blur-[200px]" />
          <div className="absolute top-[40%] -left-[250px] size-[500px] rounded-full bg-accent-blue/[0.02] blur-[180px]" />
        </div>
        
        <div className="relative flex gap-xl w-full max-w-[1440px] mx-auto h-full">
          {activeTab === 'dashboard' && (
            <>
              <div className="w-[300px] shrink-0 hidden md:block">
                <Sidebar selectedCountry={selectedCountry} onSelect={setSelectedCountry} />
              </div>
              <div className="flex-1 min-w-0">
                <ErrorBoundary fallbackMessage="Le tableau de bord a rencontré une erreur. Cliquez sur Réessayer.">
                  <Dashboard selectedCountry={selectedCountry} />
                </ErrorBoundary>
              </div>
            </>
          )}
          {activeTab === 'ranking' && (
            <ErrorBoundary fallbackMessage="Le classement a rencontré une erreur.">
              <RankingPage />
            </ErrorBoundary>
          )}
          {activeTab === 'live' && (
            <ErrorBoundary fallbackMessage="La carte en direct a rencontré une erreur.">
              <LivePage />
            </ErrorBoundary>
          )}
        </div>
      </main>
    </div>
  );
}
