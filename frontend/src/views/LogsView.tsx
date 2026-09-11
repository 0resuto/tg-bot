import React from 'react';
import { LogEvent } from '../types';

interface LogsViewProps {
  logs: LogEvent[];
  onRefresh: () => void;
}

export const LogsView: React.FC<LogsViewProps> = ({ logs, onRefresh }) => {
  return (
    <div className="flex flex-col h-full p-6 space-y-4 max-w-7xl mx-auto w-full">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide">Диагностические логи событий</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Кольцевой буфер недавних событий обработки сообщений, вызовов LLM и ошибок
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-sky-400 text-xs rounded-lg border border-slate-700 flex items-center space-x-1.5 transition cursor-pointer"
        >
          <span>🔄</span>
          <span>Обновить логи</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-inner p-4 space-y-3 font-mono text-xs">
        {logs.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-slate-500 font-sans text-sm">
            <span className="text-3xl mb-2">📋</span>
            <span>Логи событий пока пусты</span>
          </div>
        ) : (
          logs.map((log) => {
            const isError = log.status === 'error';
            return (
              <div
                key={log.id}
                className={`p-3.5 rounded-xl border space-y-2 transition ${
                  isError
                    ? 'bg-red-950/30 border-red-800/80 text-red-200'
                    : 'bg-slate-950/70 border-slate-800 text-slate-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                        isError ? 'bg-red-900 text-red-100' : 'bg-emerald-950 text-emerald-400'
                      }`}
                    >
                      {log.status.toUpperCase()}
                    </span>
                    {log.user_name && (
                      <span className="font-bold text-white">{log.user_name}</span>
                    )}
                  </div>
                  <span className="text-[10px] text-slate-500">
                    {new Date(log.timestamp).toLocaleString()}
                  </span>
                </div>

                {log.text && <div className="text-xs text-slate-200 font-sans">{log.text}</div>}

                {log.error && <div className="text-red-400 font-bold">{log.error}</div>}

                {log.traceback && (
                  <details className="text-[10px] text-slate-400 pt-1">
                    <summary className="cursor-pointer text-red-400 hover:underline">
                      Показать Traceback
                    </summary>
                    <pre className="mt-1 p-2 bg-black/80 rounded border border-red-900/40 text-red-300 overflow-x-auto whitespace-pre-wrap">
                      {log.traceback}
                    </pre>
                  </details>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
