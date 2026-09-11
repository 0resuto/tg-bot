import React from 'react';

interface MetricCardProps {
  icon: string;
  title: string;
  value: string | number;
  subtitle?: string;
  color?: 'blue' | 'emerald' | 'purple' | 'amber';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  icon,
  title,
  value,
  subtitle,
  color = 'blue',
}) => {
  const colorStyles = {
    blue: 'border-sky-500/20 bg-sky-500/5 text-sky-400',
    emerald: 'border-emerald-500/20 bg-emerald-500/5 text-emerald-400',
    purple: 'border-purple-500/20 bg-purple-500/5 text-purple-400',
    amber: 'border-amber-500/20 bg-amber-500/5 text-amber-400',
  };

  return (
    <div className={`p-4 rounded-xl border ${colorStyles[color]} bg-slate-900/60 transition-all flex flex-col justify-between`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{title}</span>
        <span className="text-xl">{icon}</span>
      </div>
      <div className="mt-2">
        <div className="text-2xl font-bold text-white tracking-tight">{value}</div>
        {subtitle && <div className="text-xs text-slate-400 mt-0.5">{subtitle}</div>}
      </div>
    </div>
  );
};
