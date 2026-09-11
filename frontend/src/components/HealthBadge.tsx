import React from 'react';
import { ChecklistItem } from '../types';

interface HealthBadgeProps {
  item: ChecklistItem;
}

export const HealthBadge: React.FC<HealthBadgeProps> = ({ item }) => {
  const isOk = item.status === 'ok';
  const icon =
    item.id === 'openai' ? '🤖' :
    item.id === 'postgres' ? '🐘' :
    item.id === 'redis' ? '⚡' : '🕸️';

  return (
    <div
      className={`p-3 rounded-xl border flex flex-col justify-between transition-all ${
        isOk
          ? 'bg-slate-900/80 border-emerald-900/40 hover:border-emerald-700/60'
          : 'bg-red-950/40 border-red-800/60'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-base">{icon}</span>
          <span className="font-semibold text-xs text-slate-200">{item.name}</span>
        </div>
        <span
          className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
            isOk
              ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/50'
              : 'bg-red-900 text-red-200 border border-red-700 animate-pulse'
          }`}
        >
          {isOk ? 'ONLINE' : 'OFFLINE'}
        </span>
      </div>

      <div className="mt-2 text-[11px] font-mono text-slate-400 truncate" title={item.target}>
        {item.target}
      </div>

      <div
        className={`mt-1 text-xs leading-tight ${
          isOk ? 'text-slate-400' : 'text-red-300 font-medium'
        }`}
      >
        {item.error || item.message}
      </div>
    </div>
  );
};
