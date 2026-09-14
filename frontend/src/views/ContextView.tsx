import React from 'react';
import { ContextMessage } from '../types';

interface ContextViewProps {
  contextMessages: ContextMessage[];
  onRefresh: () => void;
}

export const ContextView: React.FC<ContextViewProps> = React.memo(({
  contextMessages,
  onRefresh,
}) => {
  return (
    <div className="flex flex-col h-full p-6 space-y-4 max-w-7xl mx-auto w-full">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide">Контекстное окно Redis</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Скользящий буфер недавних сообщений чата, используемый ботом для понимания контекста диалога
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-sky-400 text-xs rounded-lg border border-slate-700 flex items-center space-x-1.5 transition cursor-pointer"
        >
          <span>🔄</span>
          <span>Обновить буфер</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-inner p-4 space-y-3">
        {contextMessages.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-slate-500 text-sm">
            <span className="text-3xl mb-2">💬</span>
            <span>Контекстный буфер пуст</span>
            <span className="text-xs text-slate-600 mt-1">
              В данном чате пока нет активных сообщений в окне истории
            </span>
          </div>
        ) : (
          contextMessages.map((m) => (
            <div
              key={m.message_id}
              className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-slate-700 transition space-y-1.5"
            >
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2">
                  <span className="font-bold text-sky-400">{m.display_name}</span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    ID: {m.user_id}
                  </span>
                </div>
                <div className="flex items-center space-x-2 text-[10px] text-slate-500 font-mono">
                  <span>Msg #{m.message_id}</span>
                  <span>•</span>
                  <span>{new Date(m.timestamp).toLocaleTimeString()}</span>
                </div>
              </div>
              <div className="text-slate-200 text-xs leading-relaxed">{m.text}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
});
