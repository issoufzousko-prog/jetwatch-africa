import { Plane, Clock, Leaf, DollarSign, AlertTriangle, Radio } from 'lucide-react';
import { AreaChart, Area } from 'recharts';

interface MetricsGridProps {
  data: {
    total_vols: number;
    total_heures: number;
    co2_kg: number;
    cout_usd: number;
    ratio_suspects: number;
    taux_ads_b: number;
  };
}

const generateTrend = (positive: boolean) =>
  Array.from({ length: 7 }, (_, i) => ({
    value: positive ? 10 + i * 2 + Math.random() * 5 : 20 - i * 2 + Math.random() * 5
  }));

const Sparkline = ({ data, color }: { data: { value: number }[]; color: string }) => {
  const id = `spark-${color.replace('#', '')}`;
  return (
    <AreaChart width={80} height={32} data={data}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor={color} stopOpacity={0.3} />
          <stop offset="95%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <Area
        type="monotone"
        dataKey="value"
        stroke={color}
        fill={`url(#${id})`}
        strokeWidth={1.5}
        isAnimationActive={false}
      />
    </AreaChart>
  );
};

export default function MetricsGrid({ data }: MetricsGridProps) {
  const fmt = (n: number) => new Intl.NumberFormat('en-US').format(Math.round(n));

  const metrics = [
    { label: "Volumes totaux", value: String(data.total_vols), icon: Plane, color: "#3b82f6", trend: generateTrend(true) },
    { label: "Heures de vol", value: `${data.total_heures?.toFixed(1) || 0} h`, icon: Clock, color: "#f59e0b", trend: generateTrend(true) },
    { label: "Empreinte CO\u2082", value: `${((data.co2_kg || 0) / 1000).toFixed(1)}t`, icon: Leaf, color: "#e63946", trend: generateTrend(false) },
    { label: "Estimation du cout", value: `${fmt(data.cout_usd || 0)} $`, icon: DollarSign, color: "#22c55e", trend: generateTrend(true) },
    { label: "Les suspects des vols", value: `${((data.ratio_suspects || 0) * 100).toFixed(1)}%`, icon: AlertTriangle, color: "#e63946", trend: generateTrend(false) },
    { label: "ADS-B", value: `${((data.taux_ads_b || 0) * 100).toFixed(1)}%`, icon: Radio, color: "#3b82f6", trend: generateTrend(true) },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 h-full">
      {metrics.map((m, i) => {
        const Icon = m.icon;
        return (
          <div key={i} className="glass-card p-5 flex flex-col justify-between">
            <div className="flex items-start justify-between mb-4">
              <div
                className="p-2.5 rounded-lg"
                style={{ backgroundColor: `${m.color}12`, color: m.color }}
              >
                <Icon className="w-5 h-5" />
              </div>
              <div className="opacity-50">
                <Sparkline data={m.trend} color={m.color} />
              </div>
            </div>
            <div>
              <p className="sp-micro text-muted-foreground uppercase tracking-wider mb-1">
                {m.label}
              </p>
              <h3 className="sp-h3 text-foreground tabular-nums">{m.value}</h3>
            </div>
          </div>
        );
      })}
    </div>
  );
}
