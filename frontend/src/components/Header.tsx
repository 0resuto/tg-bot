import React from 'react';
import { StatsResponse } from '../types';

interface HeaderProps {
  stats: StatsResponse | null;
  botStatus: string;
  onRefresh: () => void;
  isRefreshing: boolean;
  pollingError?: string | null;
}

export const Header: React.FC<HeaderProps> = ({
  stats,
  botStatus,
  onRefresh,
  isRefreshing,
  pollingError,
}) => {
  const isOk = !pollingError && Boolean(stats?.all_ready);

  return (
    <header className="bg-slate-900 border-b border-slate-800 px-6 py-3 flex items-center justify-between shadow-sm z-20">
      <div className="flex items-center space-x-3">
        <div className="w-9 h-9 rounded-xl bg-sky-500/20 text-sky-400 flex items-center justify-center font-bold text-lg shadow-inner">
          🤖
        </div>
        <div>
          <h1 className="text-base font-semibold text-white tracking-wide flex items-center space-x-2">
            <span>Telegram Memory Bot</span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-sky-950 text-sky-400 border border-sky-800/60 uppercase">
              Control Panel
            </span>
          </h1>
          <p className="text-xs text-slate-400">Knowledge Graph & Bot Monitoring Panel</p>
        </div>
      </div>
      <div className="flex items-center space-x-3 text-xs">
        {pollingError && (
          <div
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-amber-950/80 border border-amber-700 text-amber-300 cursor-pointer hover:bg-amber-900/80 transition"
            title={`Connection error: ${pollingError}. Click to retry.`}
            onClick={onRefresh}
          >
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
            <span className="font-medium">Backend Offline</span>
          </div>
        )}
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              pollingError
                ? 'bg-slate-500'
                : botStatus === 'calling_llm'
                  ? 'bg-yellow-400 animate-ping'
                  : botStatus === 'error'
                    ? 'bg-red-500'
                    : 'bg-emerald-400'
            }`}
          />
          <span className="text-slate-200 font-medium">
            {pollingError
              ? '⚪ Disconnected'
              : botStatus === 'calling_llm'
                ? '🟡 Generating...'
                : botStatus === 'error'
                  ? '🔴 Error'
                  : '🟢 Ready'}
          </span>
        </div>
        <div className="hidden sm:flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700">
          <span className="text-slate-400">🤖 Model:</span>
          <strong className="text-emerald-400 font-mono text-xs">
            {stats?.llm_model || 'OpenAI'}
          </strong>
        </div>
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          title={
            pollingError
              ? `Backend is unreachable: ${pollingError}`
              : isOk
                ? 'All background services are healthy'
                : 'One or more background services are degraded'
          }
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-full border transition cursor-pointer disabled:opacity-50 ${
            pollingError
              ? 'bg-amber-950/60 border-amber-800 text-amber-300 hover:bg-amber-900/80'
              : isOk
                ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300 hover:bg-emerald-900/80'
                : 'bg-red-950/60 border-red-800 text-red-300 hover:bg-red-900/80'
          }`}
        >
          <span>{isRefreshing ? '⏳' : pollingError ? '⚠️' : isOk ? '✅' : '❌'}</span>
          <span className="font-medium">
            {isRefreshing
              ? 'Checking...'
              : pollingError
                ? 'Backend Unreachable'
                : isOk
                  ? 'Services Healthy'
                  : 'Service Degradation'}
          </span>
        </button>
      </div>
    </header>
  );
};
