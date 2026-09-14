import React from 'react';
import { ChatInfo } from '../types';
import { ChatSelector } from './ChatSelector';

export type TabType =
  | 'overview'
  | 'graph'
  | 'memories'
  | 'context'
  | 'admin'
  | 'logs'
  | 'simulator';

interface SidebarProps {
  activeTab: TabType;
  onSelectTab: (tab: TabType) => void;
  chats: ChatInfo[];
  selectedChatId: number | null;
  onSelectChat: (chatId: number) => void;
  enableSimulator: boolean;
  factsCount?: number;
  messagesCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = React.memo(({
  activeTab,
  onSelectTab,
  chats,
  selectedChatId,
  onSelectChat,
  enableSimulator,
  factsCount = 0,
  messagesCount = 0,
}) => {
  const navItems = [
    { id: 'overview' as TabType, label: 'Обзор системы', icon: '📊' },
    { id: 'graph' as TabType, label: 'Граф знаний', icon: '🕸️' },
    { id: 'memories' as TabType, label: 'Факты и память', icon: '🧠', badge: factsCount },
    { id: 'context' as TabType, label: 'Контекст Redis', icon: '💬', badge: messagesCount },
    { id: 'admin' as TabType, label: 'Администрирование', icon: '⚙️' },
    { id: 'logs' as TabType, label: 'Логи событий', icon: '📋' },
  ];

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between p-4 flex-shrink-0">
      <div className="space-y-4">
        <ChatSelector
          chats={chats}
          selectedChatId={selectedChatId}
          onSelectChat={onSelectChat}
        />

        <div className="space-y-1 pt-2">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 px-3 pb-1">
            Управление и мониторинг
          </div>

          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition cursor-pointer ${
                  isActive
                    ? 'bg-sky-600 text-white shadow-sm'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <div className="flex items-center space-x-2.5">
                  <span className="text-base">{item.icon}</span>
                  <span>{item.label}</span>
                </div>
                {item.badge !== undefined && item.badge > 0 && (
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                      isActive ? 'bg-sky-700 text-white' : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {enableSimulator && (
          <div className="pt-4 border-t border-slate-800 space-y-1">
            <div className="text-[10px] font-bold uppercase tracking-wider text-amber-500/80 px-3 pb-1 flex items-center space-x-1">
              <span>🛠️</span>
              <span>Песочница тестирования</span>
            </div>
            <button
              onClick={() => onSelectTab('simulator')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition cursor-pointer border ${
                activeTab === 'simulator'
                  ? 'bg-amber-500/20 border-amber-500/80 text-amber-300 shadow-sm'
                  : 'bg-slate-800/40 border-slate-700/60 text-slate-300 hover:bg-slate-800 hover:text-white'
              }`}
            >
              <div className="flex items-center space-x-2.5">
                <span className="text-base">🎮</span>
                <span className="font-semibold">Тестовый симулятор</span>
              </div>
              <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded font-bold">
                DEV
              </span>
            </button>
          </div>
        )}
      </div>

      <div className="text-[11px] text-slate-500 pt-4 border-t border-slate-800 text-center">
        <span>Telegram Memory Bot v0.1</span>
      </div>
    </aside>
  );
});
