import React from 'react';
import { ChatInfo } from '../types';

interface ChatSelectorProps {
  chats: ChatInfo[];
  selectedChatId: number | null;
  onSelectChat: (chatId: number) => void;
}

export const ChatSelector: React.FC<ChatSelectorProps> = React.memo(({ chats, selectedChatId, onSelectChat }) => {
  return (
    <div className="flex flex-col space-y-1">
      <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Выбранный чат:</label>
      <select value={selectedChatId ?? ''} onChange={(e) => onSelectChat(Number(e.target.value))}
        className="w-full bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-lg px-3 py-2 outline-none focus:border-sky-500 transition cursor-pointer">
        {chats.length === 0 ? (
          <option value="" disabled>(Нет доступных чатов)</option>
        ) : (
          chats.map((c) => (
            <option key={c.chat_id} value={c.chat_id}>
              {c.is_simulator ? '🎮 ' : '💬 '}{c.title} ({c.chat_id})
            </option>
          ))
        )}
      </select>
    </div>
  );
});
