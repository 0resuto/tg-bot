import React, { useState } from 'react';
import { MemoryFact } from '../types';

interface MemoriesViewProps {
  memories: MemoryFact[];
  onForgetFact: (description: string) => Promise<number>;
  onRefresh: () => void;
}

export const MemoriesView: React.FC<MemoriesViewProps> = ({
  memories,
  onForgetFact,
  onRefresh,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSubject, setSelectedSubject] = useState<string>('all');
  const [deleting, setDeleting] = useState<string | null>(null);

  const subjects = Array.from(new Set(memories.map((m) => m.subject || 'Fact'))).filter(Boolean);

  const filteredMemories = memories.filter((m) => {
    const matchesSearch =
      m.fact_text.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.subject.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSubject = selectedSubject === 'all' || m.subject === selectedSubject;
    return matchesSearch && matchesSubject;
  });

  const handleDelete = async (factText: string) => {
    if (!window.confirm(`Вы действительно хотите удалить факт:\n"${factText}"?`)) return;
    setDeleting(factText);
    try {
      const deleted = await onForgetFact(factText);
      alert(`Удалено фактов: ${deleted}`);
      onRefresh();
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="flex flex-col h-full p-6 space-y-4 max-w-7xl mx-auto w-full">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide">База знаний и факты</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Факты, извлеченные Graphiti из бесед участников
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-sky-400 text-xs rounded-lg border border-slate-700 flex items-center space-x-1.5 transition cursor-pointer"
        >
          <span>🔄</span>
          <span>Обновить список</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 bg-slate-900 border border-slate-800 rounded-2xl p-3 text-xs">
        <div className="flex-1 min-w-[200px]">
          <input
            type="text"
            placeholder="Поиск по содержанию факта..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 text-xs outline-none focus:border-sky-500 transition"
          />
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-slate-400">Субъект:</span>
          <select
            value={selectedSubject}
            onChange={(e) => setSelectedSubject(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-xs outline-none focus:border-sky-500 cursor-pointer"
          >
            <option value="all">Все субъекты ({subjects.length})</option>
            {subjects.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Facts Table / List */}
      <div className="flex-1 overflow-y-auto bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-inner">
        {filteredMemories.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-slate-500 text-sm">
            <span className="text-3xl mb-2">🔍</span>
            <span>Факты не найдены</span>
            <span className="text-xs text-slate-600 mt-1">Попробуйте изменить параметры поиска</span>
          </div>
        ) : (
          <div className="divide-y divide-slate-800">
            {filteredMemories.map((m, idx) => (
              <div
                key={idx}
                className="p-4 hover:bg-slate-800/40 transition flex items-start justify-between gap-4 text-xs"
              >
                <div className="space-y-1 flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="px-2 py-0.5 rounded-md font-bold text-[11px] bg-sky-950 text-sky-400 border border-sky-800/60">
                      {m.subject || 'Fact'}
                    </span>
                    {m.created_at && (
                      <span className="text-[10px] text-slate-500 font-mono">
                        {new Date(m.created_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                  <div className="text-slate-200 text-sm leading-relaxed">{m.fact_text}</div>
                </div>

                <button
                  onClick={() => handleDelete(m.fact_text)}
                  disabled={deleting === m.fact_text}
                  title="Удалить этот факт из графа знаний"
                  className="text-xs px-2.5 py-1 rounded-md bg-red-950/40 text-red-300 hover:bg-red-900/60 border border-red-800/50 transition cursor-pointer flex items-center space-x-1 disabled:opacity-50 flex-shrink-0"
                >
                  <span>🗑️</span>
                  <span>{deleting === m.fact_text ? 'Удаление...' : 'Забыть'}</span>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
