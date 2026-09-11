import React from 'react';
import { api } from '../services/api';
import { StatsResponse } from '../types';


interface HeaderProps {
  stats: StatsResponse | null;
  botStatus: string;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  stats,
  botStatus,
  onRefresh,
  isRefreshing,
}) => {
  const isOk = stats?.all_ready ?? true;

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
          <p className="text-xs text-slate-400">Панель управления и мониторинга знаний</p>
        </div>
      </div>

      <div className="flex items-center space-x-3 text-xs">
        {/* Status Indicator */}
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              botStatus === 'calling_llm'
                ? 'bg-yellow-400 animate-ping'
                : botStatus === 'error'
                ? 'bg-red-500'
                : 'bg-emerald-400'
            }`}
          />
          <span className="text-slate-200 font-medium">
            {botStatus === 'calling_llm'
              ? '🟡 Генерация ответа...'
              : botStatus === 'error'
              ? '🔴 Ошибка'
              : '🟢 Готов к работе'}
          </span>
        </div>

        {/* Model info */}
        <div className="hidden sm:flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700">
          <span className="text-slate-400">🤖 Модель:</span>
          <strong className="text-emerald-400 font-mono text-xs">
            {stats?.llm_model || 'OpenAI'}
          </strong>
        </div>

        {/* API Key configuration button */}
        <button
          onClick={() => {
            const current = api.getApiKey();
            const input = prompt('Введите WEB_API_KEY (оставьте пустым для сброса):', current);
            if (input !== null) {
              api.setApiKey(input);
              onRefresh();
            }
          }}
          title="Настроить API-ключ"
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700 text-slate-300 hover:bg-slate-700 transition cursor-pointer"
        >
          <span>🔑</span>
          <span className="font-medium">{api.getApiKey() ? 'Ключ задан' : 'API-ключ'}</span>
        </button>

        {/* Health status badge */}

        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Проверить статус всех сервисов"
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-full border transition cursor-pointer disabled:opacity-50 ${
            isOk
              ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300 hover:bg-emerald-900/80'
              : 'bg-red-950/60 border-red-800 text-red-300 hover:bg-red-900/80'
          }`}
        >
          <span>{isRefreshing ? '⏳' : isOk ? '✅' : '❌'}</span>
          <span className="font-medium">
            {isRefreshing ? 'Проверка...' : isOk ? 'Сервисы в норме' : 'Сбой сервисов'}
          </span>
        </button>
      </div>
    </header>
  );
};
