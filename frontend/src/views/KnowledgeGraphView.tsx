import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import { GraphEdge, GraphNode, GraphResponse, SelectedGraphItem } from '../types';

interface KnowledgeGraphViewProps {
  graphData: GraphResponse | null;
  loadingGraph: boolean;
  onRefreshGraph: () => void;
}

interface EntityGroupFilter {
  group: string;
  label: string;
  icon: string;
  activeBg: string;
  activeBorder: string;
  activeText: string;
}

const KNOWN_GROUPS: EntityGroupFilter[] = [
  { group: 'Person', label: 'People', icon: '👤', activeBg: 'bg-emerald-950/60', activeBorder: 'border-emerald-600', activeText: 'text-emerald-300' },
  { group: 'Animal', label: 'Animals', icon: '🐾', activeBg: 'bg-purple-950/60', activeBorder: 'border-purple-600', activeText: 'text-purple-300' },
  { group: 'Item', label: 'Items', icon: '📦', activeBg: 'bg-blue-950/60', activeBorder: 'border-blue-600', activeText: 'text-blue-300' },
  { group: 'Location', label: 'Locations', icon: '📍', activeBg: 'bg-orange-950/60', activeBorder: 'border-orange-600', activeText: 'text-orange-300' },
  { group: 'Concept', label: 'Concepts', icon: '💡', activeBg: 'bg-yellow-950/60', activeBorder: 'border-yellow-600', activeText: 'text-yellow-300' },
  { group: 'Episodic', label: 'Episodes', icon: '💬', activeBg: 'bg-violet-950/60', activeBorder: 'border-violet-600', activeText: 'text-violet-300' },
  { group: 'Community', label: 'Communities', icon: '🌐', activeBg: 'bg-amber-950/60', activeBorder: 'border-amber-600', activeText: 'text-amber-300' },
];

export const KnowledgeGraphView: React.FC<KnowledgeGraphViewProps> = ({
  graphData,
  loadingGraph,
  onRefreshGraph,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const graphDataRef = useRef(graphData);

  useEffect(() => {
    graphDataRef.current = graphData;
  }, [graphData]);

  // Checkbox multi-select state for entity groups
  const [selectedGroups, setSelectedGroups] = useState<Set<string>>(() => new Set());
  const [physicsEnabled, setPhysicsEnabled] = useState(true);
  const [selectedItem, setSelectedItem] = useState<SelectedGraphItem | null>(null);

  // Auto-select all available groups whenever new graph data arrives
  useEffect(() => {
    if (graphData?.nodes && graphData.nodes.length > 0) {
      const all = new Set(graphData.nodes.map((n) => n.group).filter(Boolean));
      setSelectedGroups((prev) => (prev.size === 0 ? all : prev));
    }
  }, [graphData]);

  // 2x larger size spread: min 12px, max 64px (spread: 52px vs previous 26px)
  const MIN_NODE_SIZE = 12;
  const MAX_NODE_SIZE = 64;
  const DEFAULT_NODE_SIZE = 26;

  // Build filter group list based on current graph data
  const availableFilters = useMemo(() => {
    const presentGroups = new Set<string>();
    if (graphData?.nodes) {
      for (const n of graphData.nodes) {
        if (n.group) presentGroups.add(n.group);
      }
    }

    const list = KNOWN_GROUPS.filter((g) => presentGroups.has(g.group));
    for (const g of presentGroups) {
      if (!list.some((k) => k.group === g)) {
        list.push({
          group: g,
          label: g,
          icon: '⚪',
          activeBg: 'bg-sky-950/60',
          activeBorder: 'border-sky-600',
          activeText: 'text-sky-300',
        });
      }
    }
    return list;
  }, [graphData]);

  const toggleGroup = useCallback((group: string) => {
    setSelectedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) {
        next.delete(group);
      } else {
        next.add(group);
      }
      return next;
    });
  }, []);

  const selectAllGroups = useCallback(() => {
    if (!graphData?.nodes) return;
    const all = new Set(graphData.nodes.map((n) => n.group).filter(Boolean));
    setSelectedGroups(all);
  }, [graphData]);

  const clearAllGroups = useCallback(() => {
    setSelectedGroups(new Set());
  }, []);

  const filteredData = useMemo(() => {
    if (!graphData?.nodes) {
      return {
        nodes: [] as (GraphNode & { degree: number; size: number })[],
        edges: [] as GraphEdge[],
        degreeStats: { min: 0, max: 0 },
      };
    }

    const rawNodes = graphData.nodes.filter((n) => selectedGroups.has(n.group));
    const nodeIds = new Set(rawNodes.map((n) => n.id));
    const filteredEdges = (graphData.edges || []).filter(
      (e) => nodeIds.has(e.from) && nodeIds.has(e.to),
    );

    // 1. Calculate connection degree for each node in visible graph
    const degreeMap = new Map<string, number>();
    for (const node of rawNodes) {
      degreeMap.set(node.id, 0);
    }
    for (const edge of filteredEdges) {
      if (degreeMap.has(edge.from)) {
        degreeMap.set(edge.from, (degreeMap.get(edge.from) || 0) + 1);
      }
      if (degreeMap.has(edge.to)) {
        degreeMap.set(edge.to, (degreeMap.get(edge.to) || 0) + 1);
      }
    }

    // 2. Compute min and max degrees
    let minDegree = Infinity;
    let maxDegree = 0;
    for (const deg of degreeMap.values()) {
      if (deg < minDegree) minDegree = deg;
      if (deg > maxDegree) maxDegree = deg;
    }
    if (minDegree === Infinity) minDegree = 0;

    // 3. Linearly map degree to [MIN_NODE_SIZE, MAX_NODE_SIZE] (12px to 64px)
    const scaledNodes = rawNodes.map((node) => {
      const degree = degreeMap.get(node.id) || 0;
      let computedSize = DEFAULT_NODE_SIZE;

      if (maxDegree > minDegree) {
        const norm = (degree - minDegree) / (maxDegree - minDegree);
        computedSize = Math.round(MIN_NODE_SIZE + norm * (MAX_NODE_SIZE - MIN_NODE_SIZE));
      }

      return {
        ...node,
        size: computedSize,
        degree,
        title: `${node.full_name || node.label}\nCategory: ${node.group}\nConnections: ${degree}`,
      };
    });

    return {
      nodes: scaledNodes,
      edges: filteredEdges,
      degreeStats: { min: minDegree, max: maxDegree },
    };
  }, [graphData, selectedGroups]);

  const nodeCounts = useMemo(() => {
    if (!graphData?.nodes) return {} as Record<string, number>;
    const counts: Record<string, number> = { all: graphData.nodes.length };
    for (const n of graphData.nodes) {
      counts[n.group] = (counts[n.group] || 0) + 1;
    }
    return counts;
  }, [graphData]);

  useEffect(() => {
    if (!containerRef.current) return;
    if (filteredData.nodes.length === 0) {
      networkRef.current?.setData({ nodes: new DataSet([]), edges: new DataSet([]) });
      return;
    }

    const nodesDataSet = new DataSet<any>(filteredData.nodes as any);
    const edgesDataSet = new DataSet<any>(filteredData.edges as any);

    const options = {
      nodes: {
        shape: 'dot',
        font: { size: 12, color: '#f8fafc', strokeWidth: 2, strokeColor: '#0f172a' },
        borderWidth: 2,
        shadow: true,
      },
      edges: {
        length: 220,
        width: 2,
        selectionWidth: 3,
        hoverWidth: 2.5,
        smooth: { enabled: true, type: 'continuous', roundness: 0.5 },
      },
      physics: {
        enabled: physicsEnabled,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -100, // Stronger repulsion for large 64px nodes
          centralGravity: 0.008,
          springLength: 220, // ~1.83x longer connections (was 120)
          springConstant: 0.05,
          damping: 0.45,
          avoidOverlap: 0.8,
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
      const net = new Network(
        containerRef.current,
        { nodes: nodesDataSet, edges: edgesDataSet },
        options,
      );
      networkRef.current = net;

      net.on('selectNode', (params) => {
        if (params.nodes.length > 0) {
          const nId = params.nodes[0];
          const node = filteredData.nodes.find((x) => x.id === nId) || graphDataRef.current?.nodes.find((x) => x.id === nId);
          if (node) setSelectedItem({ type: 'node', data: node });
        }
      });

      net.on('selectEdge', (params) => {
        if (params.nodes.length === 0 && params.edges.length > 0) {
          const eId = params.edges[0];
          const edge = graphDataRef.current?.edges.find((x) => x.id === eId);
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

  const allSelected = availableFilters.length > 0 && availableFilters.every((g) => selectedGroups.has(g.group));

  return (
    <div className="flex flex-col h-full p-6 space-y-4">
      {/* Top Toolbar: Checkbox Filters & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900 border border-slate-800 rounded-2xl p-3.5 text-xs shadow-sm">
        <div className="flex items-center space-x-2 flex-wrap gap-y-2">
          <span className="font-semibold text-slate-300 mr-1 flex items-center space-x-1.5">
            <span>Filter Entities:</span>
          </span>

          {/* Quick Select All / Clear All buttons */}
          <div className="flex items-center space-x-1 pr-2 border-r border-slate-800">
            <button
              onClick={allSelected ? clearAllGroups : selectAllGroups}
              className={`px-2 py-1 rounded-md text-[11px] font-semibold transition cursor-pointer ${
                allSelected
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            >
              {allSelected ? '✓ All' : 'Select All'}
            </button>
            <button
              onClick={clearAllGroups}
              className="px-2 py-1 rounded-md text-[11px] text-slate-400 hover:text-rose-300 transition cursor-pointer"
            >
              Clear
            </button>
          </div>

          {/* Checkbox pills */}
          <div className="flex flex-wrap items-center gap-1.5">
            {availableFilters.map((f) => {
              const isChecked = selectedGroups.has(f.group);
              return (
                <label
                  key={f.group}
                  className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs cursor-pointer select-none transition ${
                    isChecked
                      ? `${f.activeBorder} ${f.activeBg} ${f.activeText} shadow-sm font-medium`
                      : 'border-slate-800 bg-slate-950/40 text-slate-500 hover:text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => toggleGroup(f.group)}
                    className="w-3.5 h-3.5 rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer"
                  />
                  <span>
                    {f.icon} {f.label}
                  </span>
                  <span
                    className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
                      isChecked
                        ? 'bg-slate-900/90 text-slate-200'
                        : 'bg-slate-900 text-slate-600'
                    }`}
                  >
                    {nodeCounts[f.group] || 0}
                  </span>
                </label>
              );
            })}
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={onRefreshGraph}
            disabled={loadingGraph}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-sky-300 rounded-lg border border-slate-700 flex items-center space-x-1.5 transition cursor-pointer disabled:opacity-50"
          >
            <span>{loadingGraph ? '⏳' : '🔄'}</span>
            <span>Refresh</span>
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
            <span>Center</span>
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
            <span>{physicsEnabled ? 'Physics: On' : 'Physics: Paused'}</span>
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

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 bg-slate-900/60 border border-slate-800 rounded-xl px-4 py-2 text-xs">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
          <span className="text-slate-400 font-semibold">Legend:</span>
          <span className="inline-flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#059669] border border-[#34d399]" />
            <span className="text-slate-300">👤 Person</span>
          </span>
          <span className="inline-flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#9333ea] border border-[#c084fc]" />
            <span className="text-slate-300">🐾 Animal</span>
          </span>
          <span className="inline-flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#2563eb] border border-[#60a5fa]" />
            <span className="text-slate-300">📦 Item</span>
          </span>
          <span className="inline-flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#ea580c] border border-[#fb923c]" />
            <span className="text-slate-300">📍 Location</span>
          </span>
          <span className="inline-flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#ca8a04] border border-[#fde047]" />
            <span className="text-slate-300">💡 Concept</span>
          </span>
          <span className="inline-flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rotate-45 bg-[#7c3aed] border border-[#a78bfa]" />
            <span className="text-slate-300">💬 Episode</span>
          </span>
        </div>

        {/* Dynamic Degree-to-Size Scale Indicator */}
        <div className="flex items-center space-x-2 pl-3 border-l border-slate-700/80 text-[11px] text-slate-400">
          <span className="font-semibold text-slate-300">Size by Connections:</span>
          <div className="flex items-center space-x-1.5 font-mono">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-sky-500/80" />
            <span>{MIN_NODE_SIZE}px ({filteredData.degreeStats.min})</span>
            <span className="text-slate-600">→</span>
            <span className="inline-block w-4 h-4 rounded-full bg-sky-400" />
            <span>{MAX_NODE_SIZE}px ({filteredData.degreeStats.max})</span>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-[460px] bg-slate-950 rounded-2xl border border-slate-800 relative overflow-hidden shadow-inner flex flex-col">
        {loadingGraph && (
          <div className="absolute inset-0 bg-slate-950/80 z-10 flex items-center justify-center text-sky-400 text-sm space-x-2">
            <span className="animate-spin text-xl">⏳</span>
            <span>Loading graph from Neo4j...</span>
          </div>
        )}

        {(!graphData?.nodes || graphData.nodes.length === 0) && !loadingGraph && (
          <div className="absolute inset-0 z-5 flex flex-col items-center justify-center p-6 text-center text-slate-400">
            <span className="text-4xl mb-3">🕸️</span>
            <span className="font-semibold text-slate-200 text-sm">Knowledge graph is empty</span>
            <p className="text-xs text-slate-500 max-w-md mt-1">
              When the bot monitors messages in chat, Graphiti automatically extracts entities and
              builds relationships in the knowledge graph.
            </p>
          </div>
        )}

        {filteredData.nodes.length === 0 && graphData?.nodes && graphData.nodes.length > 0 && !loadingGraph && (
          <div className="absolute inset-0 z-5 flex flex-col items-center justify-center p-6 text-center text-slate-400">
            <span className="text-3xl mb-2">🔍</span>
            <span className="font-semibold text-slate-200 text-sm">No entities match selected filters</span>
            <p className="text-xs text-slate-500 max-w-xs mt-1">
              Check one or more categories above or click &quot;Select All&quot; to display nodes.
            </p>
            <button
              onClick={selectAllGroups}
              className="mt-3 px-3 py-1 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-semibold cursor-pointer transition shadow-sm"
            >
              Select All Entities
            </button>
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
                  : (selectedItem.data as GraphEdge).full_fact ||
                    (selectedItem.data as GraphEdge).type}
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-slate-800 text-sky-300">
                {selectedItem.type === 'node' ? (selectedItem.data as GraphNode).group : 'RELATION'}
              </span>
              {selectedItem.type === 'node' && typeof (selectedItem.data as any).degree === 'number' && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-950 text-sky-300 border border-sky-800">
                  🔗 {(selectedItem.data as any).degree} {(selectedItem.data as any).degree === 1 ? 'Connection' : 'Connections'}
                </span>
              )}
            </div>
            <button
              onClick={() => setSelectedItem(null)}
              className="text-slate-400 hover:text-white font-bold px-2 py-1"
            >
              ✕
            </button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px]">
            {selectedItem.type === 'node' && typeof (selectedItem.data as any).degree === 'number' && (
              <div className="p-2 bg-slate-950/60 rounded-lg border border-sky-900/60">
                <div className="text-sky-400 text-[10px] font-medium">Connections (Degree)</div>
                <div className="text-white font-bold text-sm">
                  {(selectedItem.data as any).degree}
                  <span className="text-[10px] text-slate-500 font-normal ml-1">
                    (size: {(selectedItem.data as any).size}px)
                  </span>
                </div>
              </div>
            )}
            {Object.entries((selectedItem.data as GraphNode | GraphEdge).properties || {}).map(
              ([k, v]) => (
                <div key={k} className="p-2 bg-slate-950/60 rounded-lg border border-slate-800">
                  <div className="text-slate-500 text-[10px]">{k}</div>
                  <div className="text-slate-200 truncate" title={String(v)}>
                    {String(v)}
                  </div>
                </div>
              ),
            )}
          </div>
        </div>
      )}
    </div>
  );
};
