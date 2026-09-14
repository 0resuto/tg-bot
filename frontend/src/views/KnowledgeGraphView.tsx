import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import { GraphEdge, GraphNode, GraphResponse, SelectedGraphItem } from '../types';

interface KnowledgeGraphViewProps {
  graphData: GraphResponse | null;
  loadingGraph: boolean;
  onRefreshGraph: () => void;
}

const GROUP_MAP: Record<string, string> = {
  persons: 'Person',
  animals: 'Animal',
  items: 'Item',
  locations: 'Location',
  concepts: 'Concept',
  episodes: 'Episodic',
};

export const KnowledgeGraphView: React.FC<KnowledgeGraphViewProps> = ({
  graphData,
  loadingGraph,
  onRefreshGraph,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);

  const [graphFilter, setGraphFilter] = useState('all');
  const [physicsEnabled, setPhysicsEnabled] = useState(true);
  const [selectedItem, setSelectedItem] = useState<SelectedGraphItem | null>(null);

  const filteredData = useMemo(() => {
    if (!graphData?.nodes) return { nodes: [] as GraphNode[], edges: [] as GraphEdge[] };
    const group = GROUP_MAP[graphFilter];
    const filteredNodes = group
      ? graphData.nodes.filter((n) => n.group === group)
      : graphData.nodes;
    const nodeIds = new Set(filteredNodes.map((n) => n.id));
    const filteredEdges = (graphData.edges || []).filter(
      (e) => nodeIds.has(e.from) && nodeIds.has(e.to)
    );
    return { nodes: filteredNodes, edges: filteredEdges };
  }, [graphData, graphFilter]);

  const nodeCounts = useMemo(() => {
    if (!graphData?.nodes) return {} as Record<string, number>;
    const counts: Record<string, number> = { all: graphData.nodes.length };
    for (const n of graphData.nodes) {
      counts[n.group] = (counts[n.group] || 0) + 1;
    }
    return counts;
  }, [graphData]);

  useEffect(() => {
    if (!containerRef.current || filteredData.nodes.length === 0) return;

    const nodesDataSet = new DataSet<any>(filteredData.nodes as any);
    const edgesDataSet = new DataSet<any>(filteredData.edges as any);

    const options = {
      nodes: {
        shape: 'dot',
        size: 22,
        font: { size: 12, color: '#f8fafc', strokeWidth: 2, strokeColor: '#0f172a' },
        borderWidth: 2,
        shadow: true,
      },
      edges: {
        width: 2,
        selectionWidth: 3,
        hoverWidth: 2.5,
        smooth: { enabled: true, type: 'continuous', roundness: 0.5 },
      },
      physics: {
        enabled: physicsEnabled,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -50,
          centralGravity: 0.01,
          springLength: 120,
          springConstant: 0.08,
          damping: 0.4,
        },
        stabilization: { iterations: 120 },
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        navigationButtons: false,
        zoomView: true,
      },
    };

    if (networkRef.current) {
      networkRef.current.setData({ nodes: nodesDataSet, edges: edgesDataSet });
      networkRef.current.setOptions(options);
    } else {
      const net = new Network(containerRef.current, { nodes: nodesDataSet, edges: edgesDataSet }, options);
      networkRef.current = net;

      net.on('selectNode', (params) => {
        if (params.nodes.length > 0) {
          const nId = params.nodes[0];
          const node = graphData?.nodes.find((x) => x.id === nId);
          if (node) setSelectedItem({ type: 'node', data: node });
        }
      });

      net.on('selectEdge', (params) => {
        if (params.nodes.length === 0 && params.edges.length > 0) {
          const eId = params.edges[0];
          const edge = graphData?.edges.find((x) => x.id === eId);
          if (edge) setSelectedItem({ type: 'edge', data: edge });
        }
      });

      net.on('deselectNode', () => setSelectedItem(null));
      net.on('deselectEdge', () => setSelectedItem(null));
    }
  }, [filteredData, physicsEnabled, graphData]);

  useEffect(() => {
    return () => {
      networkRef.current?.destroy();
      networkRef.current = null;
    };
  }, []);

  const neo4jBrowserUrl = import.meta.env.VITE_NEO4J_BROWSER_URL || 'http://127.0.0.1:17474';

  return (
    <div className="flex flex-col h-full p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900 border border-slate-800 rounded-2xl p-3.5 text-xs shadow-sm">
        <div className="flex items-center space-x-2 flex-wrap gap-y-1">
          <span className="font-semibold text-slate-300 mr-1">Фильтр сущностей:</span>
          <div className="flex flex-wrap rounded-lg bg-slate-950 p-1 border border-slate-800 gap-1">
            {[
              { id: 'all', label: `Все (${nodeCounts.all || 0})`, color: 'bg-sky-600' },
              { id: 'persons', label: `👤 Люди (${nodeCounts.Person || 0})`, color: 'bg-emerald-600' },
              { id: 'animals', label: `🐾 Животные (${nodeCounts.Animal || 0})`, color: 'bg-purple-600' },
              { id: 'items', label: `📦 Предметы (${nodeCounts.Item || 0})`, color: 'bg-blue-600' },
              { id: 'locations', label: `📍 Локации (${nodeCounts.Location || 0})`, color: 'bg-orange-600' },
              { id: 'concepts', label: `💡 Концепты (${nodeCounts.Concept || 0})`, color: 'bg-yellow-600' },
              { id: 'episodes', label: `💬 Эпизоды (${nodeCounts.Episodic || 0})`, color: 'bg-violet-600' },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setGraphFilter(f.id)}
                className={`px-2.5 py-1 rounded-md text-[11px] transition cursor-pointer ${
                  graphFilter === f.id
                    ? `${f.color} text-white font-semibold shadow-sm`
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={onRefreshGraph}
            disabled={loadingGraph}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-sky-300 rounded-lg border border-slate-700 flex items-center space-x-1.5 transition cursor-pointer disabled:opacity-50"
          >
            <span>{loadingGraph ? '⏳' : '🔄'}</span>
            <span>Обновить</span>
          </button>
          <button
            onClick={() =>
              networkRef.current?.fit({
                animation: { duration: 400, easingFunction: 'easeInOutQuad' },
              })
            }
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 flex items-center space-x-1.5 transition cursor-pointer"
          >
            <span>🎯</span>
            <span>Центр</span>
          </button>
          <button
            onClick={() => setPhysicsEnabled((p) => !p)}
            className={`px-3 py-1.5 rounded-lg border flex items-center space-x-1.5 transition cursor-pointer ${
              physicsEnabled
                ? 'bg-sky-950 border-sky-700 text-sky-300'
                : 'bg-slate-800 border-slate-700 text-slate-400'
            }`}
          >
            <span>{physicsEnabled ? '⏸️' : '▶️'}</span>
            <span>{physicsEnabled ? 'Физика: Вкл' : 'Физика: Пауза'}</span>
          </button>
          <a
            href={neo4jBrowserUrl}
            target="_blank"
            rel="noreferrer"
            className="px-3 py-1.5 bg-emerald-950/80 hover:bg-emerald-900 text-emerald-300 rounded-lg border border-emerald-800 flex items-center space-x-1.5 transition"
          >
            <span>🌐</span>
            <span>Neo4j Browser</span>
          </a>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 bg-slate-900/60 border border-slate-800 rounded-xl px-4 py-2 text-xs">
        <span className="text-slate-400 font-semibold">Легенда:</span>
        <span className="inline-flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#059669] border border-[#34d399]" />
          <span className="text-slate-300">👤 Человек</span>
        </span>
        <span className="inline-flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#9333ea] border border-[#c084fc]" />
          <span className="text-slate-300">🐾 Животное</span>
        </span>
        <span className="inline-flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#2563eb] border border-[#60a5fa]" />
          <span className="text-slate-300">📦 Предмет</span>
        </span>
        <span className="inline-flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#ea580c] border border-[#fb923c]" />
          <span className="text-slate-300">📍 Локация</span>
        </span>
        <span className="inline-flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#ca8a04] border border-[#fde047]" />
          <span className="text-slate-300">💡 Концепт</span>
        </span>
        <span className="inline-flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rotate-45 bg-[#7c3aed] border border-[#a78bfa]" />
          <span className="text-slate-300">💬 Эпизод</span>
        </span>
      </div>

      <div className="flex-1 min-h-[460px] bg-slate-950 rounded-2xl border border-slate-800 relative overflow-hidden shadow-inner flex flex-col">
        {loadingGraph && (
          <div className="absolute inset-0 bg-slate-950/80 z-10 flex items-center justify-center text-sky-400 text-sm space-x-2">
            <span className="animate-spin text-xl">⏳</span>
            <span>Загрузка графа из базы Neo4j...</span>
          </div>
        )}

        {(!graphData?.nodes || graphData.nodes.length === 0) && !loadingGraph && (
          <div className="absolute inset-0 z-5 flex flex-col items-center justify-center p-6 text-center text-slate-400">
            <span className="text-4xl mb-3">🕸️</span>
            <span className="font-semibold text-slate-200 text-sm">Граф знаний пуст</span>
            <p className="text-xs text-slate-500 max-w-md mt-1">
              Когда бот наблюдает за сообщениями в чате, Graphiti автоматически извлекает сущности и
              строит связи в графе знаний.
            </p>
          </div>
        )}

        <div ref={containerRef} className="w-full h-full" />
      </div>

      {selectedItem && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 text-xs shadow-lg">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2">
            <div className="flex items-center space-x-2">
              <span className="text-lg">{selectedItem.type === 'node' ? '📍' : '🔗'}</span>
              <span className="font-bold text-white text-sm">
                {selectedItem.type === 'node'
                  ? (selectedItem.data as { full_name?: string }).full_name
                  : (selectedItem.data as GraphEdge).full_fact || (selectedItem.data as GraphEdge).type}
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-slate-800 text-sky-300">
                {selectedItem.type === 'node' ? (selectedItem.data as GraphNode).group : 'СВЯЗЬ'}
              </span>
            </div>
            <button
              onClick={() => setSelectedItem(null)}
              className="text-slate-400 hover:text-white font-bold px-2 py-1"
            >
              ✕
            </button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px]">
            {Object.entries((selectedItem.data as GraphNode | GraphEdge).properties || {}).map(([k, v]) => (
              <div key={k} className="p-2 bg-slate-950/60 rounded-lg border border-slate-800">
                <div className="text-slate-500 text-[10px]">{k}</div>
                <div className="text-slate-200 truncate" title={String(v)}>
                  {String(v)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
