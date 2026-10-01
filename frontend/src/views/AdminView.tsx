import React from 'react';
import { StatsResponse } from '../types';

interface AdminViewProps {
  stats: StatsResponse | null;
  selectedChatId: number | null;
}

export const AdminView: React.FC<AdminViewProps> = React.memo(({ stats, selectedChatId }) => {
  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto overflow-y-auto">
      <div>
        <h2 className="text-xl font-bold text-white tracking-wide">System Settings</h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Service and model configurations {selectedChatId ? `(Chat ${selectedChatId})` : ''}
        </p>
      </div>

      {/* AI and Memory Configuration Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center space-x-2">
            <span>⚙️</span>
            <span>AI & Memory Parameters</span>
          </h3>
          <p className="text-xs text-slate-400 mt-1">Active services and model configuration</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
            <div className="text-slate-400">Response Model:</div>
            <div className="text-sm font-bold text-purple-400 mt-1 font-mono truncate">
              {stats?.llm_model || 'OpenAI'}
            </div>
          </div>
          <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
            <div className="text-slate-400">Memory Backend:</div>
            <div className="text-sm font-bold text-emerald-400 mt-1 font-mono truncate">
              {stats?.memory_backend || 'Neo4j + Graphiti'}
            </div>
          </div>
          <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
            <div className="text-slate-400">Bot Aliases:</div>
            <div className="text-sm font-bold text-sky-400 mt-1 font-mono truncate">
              {stats?.bot_names?.join(', ') || 'Bot'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});
