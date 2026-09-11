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

export const OverviewView: React.FC<OverviewViewProps> = ({
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
  const todayTokens = stats?.token_stats?.today_tokens || 0;
  const monthTokens = stats?.token_stats?.month_tokens || 0;

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-w-7xl mx-auto">
      {/* Page Title */}
      <div>
        <h2 className="text-xl font-bold text-white tracking-wide">Обзор состояния системы</h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Оперативный статус инфраструктуры, памяти и потребления ресурсов
        </p>
      </div>

      {/* KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          icon="🧠"
          title="Факты в памяти"
          value={factsCount}
          subtitle="Сформированные утверждения"
          color="blue"
        />
        <MetricCard
          icon="🕸️"
          title="Граф знаний"
          value={`${graphNodesCount} / ${graphEdgesCount}`}
          subtitle="Узлов / Связей в Neo4j"
          color="purple"
        />
        <MetricCard
          icon="💬"
          title="Контекст диалогов"
          value={contextMessagesCount}
          subtitle="Сообщений в окне Redis"
          color="emerald"
        />
        <MetricCard
          icon="🪙"
          title="Токены LLM"
          value={todayTokens.toLocaleString()}
          subtitle={`За месяц: ${monthTokens.toLocaleString()}`}
          color="amber"
        />
      </div>

      {/* Infrastructure Health Checklist */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <span>🛠️</span>
              <span>Состояние сервисов инфраструктуры</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Мониторинг подключений к БД, брокерам и провайдеру нейросетей
            </p>
          </div>
          <button
            onClick={onRefreshHealth}
            disabled={isRefreshingHealth}
            className="text-xs bg-slate-800 hover:bg-slate-700 text-sky-400 px-3 py-1.5 rounded-lg border border-slate-700 flex items-center space-x-1.5 transition cursor-pointer disabled:opacity-50"
          >
            <span>{isRefreshingHealth ? '⏳' : '🔄'}</span>
            <span>{isRefreshingHealth ? 'Проверка...' : 'Перепроверить'}</span>
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
            <h4 className="text-sm font-bold text-white mt-3">Интерактивный граф знаний</h4>
            <p className="text-xs text-slate-400 mt-1">
              Визуализация связей между людьми, локациями, предметами и концептами в Neo4j.
            </p>
          </div>
          <span className="text-xs text-sky-400 font-medium mt-4 inline-flex items-center space-x-1">
            <span>Открыть граф</span>
            <span>→</span>
          </span>
        </div>

        <div
          onClick={() => onNavigate('memories')}
          className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 hover:border-purple-500/50 hover:bg-slate-900/80 transition cursor-pointer flex flex-col justify-between"
        >
          <div>
            <span className="text-2xl">🧠</span>
            <h4 className="text-sm font-bold text-white mt-3">Реестр фактов и забывание</h4>
            <p className="text-xs text-slate-400 mt-1">
              Поиск фактов о пользователях и удаление неактуальной информации через forget-пайплайн.
            </p>
          </div>
          <span className="text-xs text-purple-400 font-medium mt-4 inline-flex items-center space-x-1">
            <span>Просмотреть факты</span>
            <span>→</span>
          </span>
        </div>

        <div
          onClick={() => onNavigate('admin')}
          className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 hover:border-emerald-500/50 hover:bg-slate-900/80 transition cursor-pointer flex flex-col justify-between"
        >
          <div>
            <span className="text-2xl">⚙️</span>
            <h4 className="text-sm font-bold text-white mt-3">Администрирование и фильтры</h4>
            <p className="text-xs text-slate-400 mt-1">
              Тестирование фильтра конфиденциальных тем, статистика токенов и безопасность.
            </p>
          </div>
          <span className="text-xs text-emerald-400 font-medium mt-4 inline-flex items-center space-x-1">
            <span>Инструменты</span>
            <span>→</span>
          </span>
        </div>
      </div>
    </div>
  );
};
