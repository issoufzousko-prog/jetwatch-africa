import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { Plane, AlertCircle } from 'lucide-react';

interface FleetReportProps {
  country: string;
}

interface PlaneImage {
  icao24: string;
  url: string | null;
}

const imageCache: Record<string, string | null> = {};

export default function FleetReport({ country }: FleetReportProps) {
  const [fleet, setFleet] = useState<any[]>([]);
  const [images, setImages] = useState<Record<string, string | null>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    
    api.getFleet(country)
      .then(data => {
        if (!isMounted) return;
        setFleet(data.flotte || []);
        
        // Fetch images from Planespotters API
        const fetchImages = async () => {
          const newImages: Record<string, string | null> = {};
          
          for (const jet of data.flotte) {
            if (!jet.icao24) continue;
            
            const hex = jet.icao24.toLowerCase();
            
            // Check cache first
            if (imageCache[hex] !== undefined) {
              newImages[jet.icao24] = imageCache[hex];
              continue;
            }
            
            try {
              const res = await fetch(`https://api.planespotters.net/pub/photos/hex/${hex}`);
              if (res.ok) {
                const photoData = await res.json();
                if (photoData.photos && photoData.photos.length > 0) {
                  newImages[jet.icao24] = photoData.photos[0].thumbnail_large.src;
                } else {
                  newImages[jet.icao24] = null;
                }
              } else {
                // Handle 429 or 404
                newImages[jet.icao24] = null;
              }
            } catch (err) {
              console.error(`Erreur image pour ${hex}:`, err);
              newImages[jet.icao24] = null;
            }
            
            // Save to cache
            imageCache[hex] = newImages[jet.icao24];
            
            // Sleep to avoid rate limiting if we have multiple new jets
            await new Promise(r => setTimeout(r, 250));
          }
          
          if (isMounted) setImages(newImages);
        };
        
        fetchImages();
      })
      .catch(err => {
        if (isMounted) setError(err.message);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => { isMounted = false; };
  }, [country]);

  if (loading) {
    return (
      <div className="glass-card p-xl flex justify-center items-center h-48 animate-pulse">
        <p className="sp-caption text-muted-foreground">Chargement de la flotte...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card p-xl border-accent-red/30 text-center">
        <AlertCircle className="w-8 h-8 text-accent-red mx-auto mb-2" />
        <p className="sp-body text-accent-red">Impossible de charger la flotte.</p>
        <p className="sp-micro text-accent-red/70 mt-2 font-mono">{error}</p>
      </div>
    );
  }

  if (fleet.length === 0) {
    return (
      <div className="glass-card p-xl text-center">
        <Plane className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-50" />
        <p className="sp-body text-muted-foreground">Aucun jet enregistré pour ce pays.</p>
      </div>
    );
  }

  return (
    <div className="mb-xl">
      <h3 className="sp-h4 text-foreground mb-md">Rapport de Flotte</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-md">
        {fleet.map((jet, idx) => (
          <div key={idx} className="glass-card overflow-hidden group hover:border-glass-border-hover transition-colors">
            {/* Image container */}
            <div className="h-48 bg-black/50 relative overflow-hidden flex items-center justify-center">
              {images[jet.icao24] ? (
                <img 
                  src={images[jet.icao24]!} 
                  alt={jet.tail_number}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                />
              ) : (
                <div className="text-center opacity-30">
                  <Plane className="w-12 h-12 text-white mx-auto mb-2" />
                  <span className="sp-micro text-white">Pas de photo disponible</span>
                </div>
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent" />
              <div className="absolute bottom-3 left-3 flex items-center gap-2">
                <span className="px-2 py-0.5 bg-accent-blue text-white sp-micro rounded font-mono">
                  {jet.tail_number || 'INCONNU'}
                </span>
                {jet.verifie && (
                  <span className="px-2 py-0.5 bg-accent-green/20 text-accent-green border border-accent-green/30 sp-micro rounded">
                    Vérifié
                  </span>
                )}
              </div>
            </div>
            
            {/* Details */}
            <div className="p-sm">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <div className="sp-micro text-muted-foreground font-mono">ICAO: {jet.icao24 ? jet.icao24.toUpperCase() : 'N/A'}</div>
                </div>
              </div>
              <p className="sp-body text-foreground truncate">{jet.description || 'Modèle inconnu'}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
