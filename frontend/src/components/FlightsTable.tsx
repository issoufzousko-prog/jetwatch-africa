import { Plane } from 'lucide-react';

interface Flight {
  id: number;
  icao24: string;
  tail_number: string;
  callsign: string;
  departure_airport: string | null;
  arrival_airport: string | null;
  departure_time: number;
  arrival_time: number | null;
  duration_minutes: number | null;
  classification: string | null;
  co2_kg: number | null;
}

export default function FlightsTable({ flights }: { flights: Flight[] }) {
  return (
    <div className="glass-card overflow-hidden">
      <div className="flex items-center justify-between p-lg border-b border-glass-border">
        <div className="flex items-center gap-sm">
          <Plane className="w-4 h-4 text-muted-foreground" />
          <h3 className="sp-h5 text-foreground">Historique des vols</h3>
        </div>
        <span className="sp-data-sm text-muted-foreground">{flights.length} vols</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-glass-border">
              <th className="text-left sp-micro text-muted-foreground uppercase tracking-wider p-lg pb-sm">Date</th>
              <th className="text-left sp-micro text-muted-foreground uppercase tracking-wider p-lg pb-sm">Départ</th>
              <th className="text-left sp-micro text-muted-foreground uppercase tracking-wider p-lg pb-sm">Arrivée</th>
              <th className="text-right sp-micro text-muted-foreground uppercase tracking-wider p-lg pb-sm">Durée</th>
              <th className="text-right sp-micro text-muted-foreground uppercase tracking-wider p-lg pb-sm">CO₂</th>
              <th className="text-center sp-micro text-muted-foreground uppercase tracking-wider p-lg pb-sm">Statut</th>
            </tr>
          </thead>
          <tbody>
            {flights.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-lg text-center text-muted-foreground sp-body">
                  Aucun historique de vol disponible en base de données.
                </td>
              </tr>
            ) : (
              flights.map((f, i) => {
                const date = new Date(f.departure_time * 1000).toLocaleDateString('fr-FR', {
                  day: 'numeric', month: 'short', year: 'numeric'
                });
                const duree = f.duration_minutes ? (f.duration_minutes / 60).toFixed(1) : '-';
                const co2 = f.co2_kg ? (f.co2_kg / 1000).toFixed(1) + 't' : '-';
                const suspect = f.classification === 'personnel';
                const normal = f.classification === 'officiel';
                
                return (
                  <tr key={i} className="border-b border-glass-border last:border-0 dark:hover:bg-white/[0.03]">
                    <td className="p-lg sp-data text-foreground">{date}</td>
                    <td className="p-lg sp-body text-foreground">{f.departure_airport || 'Inconnu'}</td>
                    <td className="p-lg sp-body text-foreground">{f.arrival_airport || (f.arrival_time ? 'Inconnu' : 'En vol')}</td>
                    <td className="p-lg sp-data text-muted-foreground text-right">{duree}h</td>
                    <td className="p-lg sp-data text-muted-foreground text-right">{co2}</td>
                    <td className="p-lg text-center">
                      {suspect ? <span className="badge-critique">Suspect</span> : 
                       normal ? <span className="badge-normal">Officiel</span> :
                       <span className="text-muted-foreground sp-micro bg-glass px-2 py-1 rounded">Non classifié</span>}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
