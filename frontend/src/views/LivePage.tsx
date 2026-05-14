import { useEffect, useRef, useState } from 'react';
import { Plane, Radio, EyeOff, Eye } from 'lucide-react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { api } from '../services/api';

interface LiveTrajectory {
  id: number;
  icao24: string;
  tail_number: string;
  pays: string;
  callsign: string;
  duration_minutes: number;
  current_pos: [number, number];
  current_track: number;
  path: [number, number][];
}

// Génère une couleur unique basée sur le nom du pays
function getColorForCountry(pays: string) {
  let hash = 0;
  for (let i = 0; i < pays.length; i++) hash = pays.charCodeAt(i) + ((hash << 5) - hash);
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 80%, 60%)`;
}

function createPlaneIcon(color: string, track: number) {
  // Icône d'avion (style Material Flight, pointant à 0°) avec animation radar (ping)
  const svg = `
    <div class="relative flex items-center justify-center" style="width: 32px; height: 32px;">
      <div class="absolute inset-0 rounded-full opacity-30 animate-ping" style="background-color: ${color};"></div>
      <div class="absolute inset-0 rounded-full opacity-10" style="border: 1px solid ${color};"></div>
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="${color}" stroke="#0a0a0c" stroke-width="0.8" style="transform: rotate(${track}deg); width: 28px; height: 28px; filter: drop-shadow(0 0 6px ${color}); z-index: 10;">
        <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z" />
      </svg>
    </div>
  `;
  return L.divIcon({
    className: 'bg-transparent border-none',
    html: svg,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
}

// Icon pour les photos (lieux de départ/arrivée)
function createPhotoIcon(label: string, isArrival: boolean = false) {
  // Image placeholder dynamique selon le type (départ ou arrivée)
  const imgUrl = isArrival 
    ? "https://images.unsplash.com/photo-1496568816309-51d7c20e3b21?auto=format&fit=crop&q=80&w=100&h=100" 
    : "https://images.unsplash.com/photo-1542314831-c6a4d14effd0?auto=format&fit=crop&q=80&w=100&h=100";
    
  return L.divIcon({
    className: '',
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    html: `<div style="
      width:40px;height:40px;border-radius:8px;
      background-image:url('${imgUrl}');background-size:cover;
      border:2px solid ${isArrival ? '#22c55e' : '#f59e0b'};
      box-shadow:0 4px 12px rgba(0,0,0,0.5);
      display:flex;align-items:flex-end;justify-content:center;
      position:relative;
    "><div style="position:absolute;bottom:-18px;background:#141418;color:white;font-size:10px;padding:2px 4px;border-radius:4px;white-space:nowrap;border:1px solid rgba(255,255,255,0.1);">${label}</div></div>`,
  });
}

export default function LivePage() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const layersRef = useRef<L.LayerGroup | null>(null);
  
  const [trajectories, setTrajectories] = useState<LiveTrajectory[]>([]);
  const [isolatedFlightId, setIsolatedFlightId] = useState<number | null>(null);
  const [predictions, setPredictions] = useState<any[]>([]);

  // Fetching data
  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await api.getLiveTrajectories();
        setTrajectories(data);
        
        // Fetch predictions if a flight is isolated
        if (isolatedFlightId) {
          const isolatedFlight = data.find((t: LiveTrajectory) => t.id === isolatedFlightId);
          if (isolatedFlight && isolatedFlight.icao24) {
            const predData = await api.getPredictions(isolatedFlight.icao24);
            setPredictions(predData.predictions || []);
          }
        } else {
            setPredictions([]);
        }
      } catch (error) {
        console.error("Erreur chargement trajectoires:", error);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 15000); // 15 secondes
    return () => clearInterval(interval);
  }, [isolatedFlightId]);

  // Map initialization
  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;
    const map = L.map(mapRef.current, {
      center: [5, 20],
      zoom: 3.5,
      zoomControl: false,
      attributionControl: false,
    });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 18 }).addTo(map);
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    
    layersRef.current = L.layerGroup().addTo(map);
    mapInstance.current = map;
    
    return () => { map.remove(); mapInstance.current = null; };
  }, []);

  // Drawing elements
  useEffect(() => {
    if (!mapInstance.current || !layersRef.current) return;
    const group = layersRef.current;
    group.clearLayers();

    const activeFlights = isolatedFlightId 
      ? trajectories.filter(t => t.id === isolatedFlightId) 
      : trajectories;

    activeFlights.forEach(t => {
      if (t.path.length === 0) return;
      const color = getColorForCountry(t.pays);

      // Trajectoire (Polyline)
      if (t.path.length > 1) {
        L.polyline(t.path, {
          color: color,
          weight: 3,
          opacity: 0.7,
          dashArray: '10, 10',
          lineCap: 'round',
        }).addTo(group);
      }

      // Marqueur de Départ (Photo du lieu)
      if (t.path.length > 0) {
        const startPos = t.path[0];
        L.marker(startPos, { icon: createPhotoIcon("Origine") }).addTo(group);
      }

      // L'avion lui-même
      const marker = L.marker(t.current_pos, { icon: createPlaneIcon(color, t.current_track) });
      marker.bindPopup(`
        <div style="font-family:Inter,sans-serif;color:#fafafa;background:#141418;border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:16px;min-width:200px;box-shadow:0 8px 32px rgba(0,0,0,0.6);">
          <div class="notranslate" style="font-size:14px;font-weight:700;margin-bottom:4px;color:${color}">${t.pays}</div>
          <div style="font-size:12px;color:#71717a;margin-bottom:8px;">Jet: ${t.tail_number}</div>
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="font-size:11px;color:#71717a;">Callsign</span>
            <span style="font-size:13px;font-weight:600;">${t.callsign}</span>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="font-size:11px;color:#71717a;">En vol depuis</span>
            <span style="font-size:13px;font-weight:600;">${t.duration_minutes} min</span>
          </div>
          <div style="display:flex;justify-content:space-between;">
            <span style="font-size:11px;color:#71717a;">Cap</span>
            <span style="font-size:13px;font-weight:600;">${t.current_track}°</span>
          </div>
        </div>
      `, { className: 'custom-popup', closeButton: false });
      marker.addTo(group);
    });

    // Dessiner les prédictions (cibles animées) si vol isolé
    if (isolatedFlightId && predictions.length > 0) {
      predictions.forEach(p => {
        if (p.probability <= 7) return; // Disparition si probabilité faible

        // Couleur basée sur la probabilité
        const targetColor = p.probability > 70 ? '#ef4444' : (p.probability > 40 ? '#f59e0b' : '#3b82f6');
        
        // Cercle cible
        const circle = L.circle([p.lat, p.lon], {
          color: targetColor,
          fillColor: targetColor,
          fillOpacity: 0.2,
          radius: 50000, // 50km
          weight: 2,
          dashArray: '5, 5'
        }).addTo(group);

        // Tooltip prédiction
        circle.bindTooltip(`
          <div style="font-family:Inter,sans-serif;background:#141418;color:white;border:1px solid ${targetColor};padding:8px;border-radius:8px;">
            <div style="font-weight:bold;font-size:14px;color:${targetColor}">${p.city} (${p.probability}%)</div>
            <div style="font-size:11px;color:#a1a1aa;margin-top:2px;">Type: ${p.type}</div>
            ${p.osint_findings ? `<div style="font-size:10px;margin-top:4px;color:#fbbf24">🎯 OSINT Hit!</div>` : ''}
          </div>
        `, { direction: 'top', className: 'custom-tooltip bg-transparent border-none shadow-none' });
      });
    }

    // Optionnel : Recadrer la carte sur l'avion isolé
    if (isolatedFlightId && activeFlights.length > 0) {
        mapInstance.current.setView(activeFlights[0].current_pos, 6, { animate: true });
    }

  }, [trajectories, isolatedFlightId, predictions]);

  return (
    <div className="flex flex-col gap-xl w-full">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-md">
        <div>
          <div className="flex items-center gap-sm mb-2xs">
            <div className="p-xs rounded-lg bg-accent-blue/10">
              <Radio className="w-5 h-5 text-accent-blue animate-pulse" />
            </div>
            <h2 className="sp-h2 text-foreground">Surveillance de l'espace aérien</h2>
          </div>
          <p className="sp-body text-muted-foreground">
            Trajectoires en direct. {trajectories.length} avion(s) actuellement en vol.
          </p>
        </div>

        {/* Isolation Control */}
        {trajectories.length > 0 && (
          <div className="flex items-center gap-sm bg-glass border border-glass-border rounded-lg p-2">
            <span className="sp-micro text-muted-foreground uppercase ml-2">Trafic :</span>
            <select 
              className="bg-transparent border-none text-foreground text-sm focus:outline-none focus:ring-0 cursor-pointer"
              value={isolatedFlightId || "all"}
              onChange={(e) => setIsolatedFlightId(e.target.value === "all" ? null : Number(e.target.value))}
            >
              <option value="all" className="bg-[#141418]">Global (Tous les pays)</option>
              {trajectories.map(t => (
                <option key={t.id} value={t.id} className="bg-[#141418] notranslate">
                  {t.pays} - {t.tail_number}
                </option>
              ))}
            </select>
            <button 
              onClick={() => setIsolatedFlightId(null)}
              className={`p-1.5 rounded-md transition-colors ${isolatedFlightId ? 'bg-accent-blue/20 text-accent-blue hover:bg-accent-blue/30' : 'text-muted-foreground'}`}
              title="Réinitialiser la vue globale"
            >
              {isolatedFlightId ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
            </button>
          </div>
        )}
      </div>

      {/* Map Container */}
      <div className="glass-card overflow-hidden h-[600px] lg:h-[700px] relative rounded-2xl border border-glass-border">
        {trajectories.length === 0 && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#0a0a0c]/80 backdrop-blur-sm">
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="relative">
                <Plane className="w-12 h-12 text-muted-foreground/50 animate-bounce" />
                <div className="absolute inset-0 border-4 border-t-accent-blue border-r-transparent border-b-transparent border-l-transparent rounded-full animate-spin"></div>
              </div>
              <p className="sp-body text-foreground">Recherche de signaux ADSB...</p>
              <p className="sp-micro text-muted-foreground">Aucun vol présidentiel détecté pour le moment.</p>
            </div>
          </div>
        )}
        <div ref={mapRef} className="w-full h-full z-10" />
      </div>
    </div>
  );
}
