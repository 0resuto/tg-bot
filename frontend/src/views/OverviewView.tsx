import React from 'react';
import { HealthBadge } from '../components/HealthBadge';
import { MetricCard } from '../components/MetricCard';
import { ChecklistItem, StatsResponse } from '../types';

interface OverviewViewProps {
  stats: StatsResponse | null;
  checklist: ChecklistItem[];
  factsCount: number;
  graphNodesCount: number;
  graphEdgesCount: number;
  contextMessagesCount: number;
  onNavigate: (tab: any) => void;
  onRefreshHealth: () => void;
  isRefreshingHealth: boolean;
}

export const OverviewView: React.FC<OverviewViewProps> = React.memo(
  ({
    stats,
    checklist,
    factsCount,
    graphNodesCount,
    graphEdgesCount,
    contextMessagesCount,
    onNavigate,
    onRefreshHealth,
    isRefreshingHealth,
  }) => {
    return (
      <div className="p-6 space-y-6 overflow-y-auto max-w-7xl mx-auto">
        {/* Page Title */}
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide">System Status Overview</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Operational status of infrastructure, memory, and resource usage
          </p>
        </div>

        {/* KPI Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            icon="🧠"
            title="Memory Facts"
            value={factsCount}
            subtitle="Extracted assertions"
            color="blue"
          />
          <MetricCard
            icon="🕸️"
            title="Knowledge Graph"
            value={`${graphNodesCount} / ${graphEdgesCount}`}
            subtitle="Nodes / Edges in Neo4j"
            color="purple"
          />
          <MetricCard
            icon="💬"
            title="Dialogue Context"
            value={contextMessagesCount}
            subtitle="Messages in Redis window"
            color="emerald"
          />
          <MetricCard
            icon="🤖"
            title="LLM Model"
            value={stats?.llm_model || 'gpt-4o'}
            subtitle={`Memory: ${stats?.memory_backend || 'Neo4j'}`}
            color="amber"
          />
        </div>

        {/* Infrastructure Health Checklist */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <span>🛠️</span>
                <span>Infrastructure Services Health</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Connection status for databases, cache, and AI providers
              </p>
            </div>
            <button
              onClick={onRefreshHealth}
              disabled={isRefreshingHealth}
              className="text-xs bg-slate-800 hover:bg-slate-700 text-sky-400 px-3 py-1.5 rounded-lg border border-slate-700 flex items-center space-x-1.5 transition cursor-pointer disabled:opacity-50"
            >
              <span>{isRefreshingHealth ? '⏳' : '🔄'}</span>
              <span>{isRefreshingHealth ? 'Checking...' : 'Re-check'}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {checklist.map((item) => (
              <HealthBadge key={item.id} item={item} />
            ))}
          </div>
        </div>

        {/* Quick Access Tiles */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div
            onClick={() => onNavigate('graph')}
            className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 hover:border-sky-500/50 hover:bg-slate-900/80 transition cursor-pointer flex flex-col justify-between"
          >
            <div>
              <span className="text-2xl">🕸️</span>
              <h4 className="text-sm font-bold text-white mt-3">Interactive Knowledge Graph</h4>
              <p className="text-xs text-slate-400 mt-1">
                Visualization of entities and relationships across participants, locations, and
                concepts.
              </p>
            </div>
            <span className="text-xs text-sky-400 font-medium mt-4 inline-flex items-center space-x-1">
              <span>Open Graph</span>
              <span>→</span>
            </span>
          </div>

          <div
            onClick={() => onNavigate('memories')}
            className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 hover:border-purple-500/50 hover:bg-slate-900/80 transition cursor-pointer flex flex-col justify-between"
          >
            <div>
              <span className="text-2xl">🧠</span>
              <h4 className="text-sm font-bold text-white mt-3">Memory Facts & Retrieval</h4>
              <p className="text-xs text-slate-400 mt-1">
                Inspection of extracted episodic facts and user assertions.
              </p>
            </div>
            <span className="text-xs text-purple-400 font-medium mt-4 inline-flex items-center space-x-1">
              <span>View Facts</span>
              <span>→</span>
            </span>
          </div>

          <div
            onClick={() => onNavigate('admin')}
            className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 hover:border-emerald-500/50 hover:bg-slate-900/80 transition cursor-pointer flex flex-col justify-between"
          >
            <div>
              <span className="text-2xl">⚙️</span>
              <h4 className="text-sm font-bold text-white mt-3">System Configuration</h4>
              <p className="text-xs text-slate-400 mt-1">
                Model settings, persona configuration, and operational parameters.
              </p>
            </div>
            <span className="text-xs text-emerald-400 font-medium mt-4 inline-flex items-center space-x-1">
              <span>Settings</span>
              <span>→</span>
            </span>
          </div>
        </div>
      </div>
    );
  },
);
