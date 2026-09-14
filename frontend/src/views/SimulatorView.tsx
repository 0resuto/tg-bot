import React, { useEffect, useRef, useState } from 'react';
import { PresetUser, SimulatedMessage, SimulatorPreset } from '../types';

interface SimulatorViewProps {
  users: PresetUser[];
  presets: SimulatorPreset[];
  messages: SimulatedMessage[];
  onSendMessage: (user: PresetUser, text: string, replyToBot: boolean) => Promise<void>;
  loading: boolean;
  botName: string;
}

export const SimulatorView: React.FC<SimulatorViewProps> = ({
  users,
  presets,
  messages,
  onSendMessage,
  loading,
  botName,
}) => {
  const [currentUser, setCurrentUser] = useState<PresetUser>(users[0] || { id: 1, name: 'Alice', avatar: '👩', role: 'Member' });
  const [replyToBot, setReplyToBot] = useState(false);
  const [inputText, setInputText] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (users.length > 0) {
      if (!users.some((u) => u.id === currentUser?.id)) {
        setCurrentUser(users[0]);
      }
    }
  }, [users]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputText.trim() || loading) return;
    const text = inputText;
    setInputText('');
    await onSendMessage(currentUser, text, replyToBot);
    setReplyToBot(false);
  };

  const handlePresetClick = (preset: SimulatorPreset) => {
    const matchedUser = users.find((u) => u.name === preset.user) || currentUser;
    setCurrentUser(matchedUser);
    setInputText(preset.text);
  };

  return (
    <div className="flex flex-col h-full bg-slate-950">
      <div className="bg-slate-900/90 border-b border-slate-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-7 h-7 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-sm">
            🎮
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <span>Песочница тестирования диалогов (Simulator Sandbox)</span>
              <span className="text-[10px] bg-amber-950 text-amber-300 border border-amber-800 px-2 py-0.5 rounded-full font-bold">
                DEV ONLY
              </span>
            </h3>
            <p className="text-[11px] text-slate-400">
              Симуляция группового чата с проверкой реакции бота, фильтрации и извлечения памяти
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3 text-xs">
          <span className="text-slate-400">Говорить от имени:</span>
          <div className="flex space-x-1.5">
            {users.map((u) => (
              <button
                key={u.id}
                onClick={() => setCurrentUser(u)}
                className={`px-2.5 py-1 rounded-lg transition-all flex items-center space-x-1 cursor-pointer ${
                  currentUser?.id === u.id
                    ? 'bg-sky-500 text-white font-semibold shadow-sm'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}
              >
                <span>{u.avatar}</span>
                <span>{u.name}</span>
              </button>
            ))}
          </div>

          <label className="flex items-center space-x-1.5 text-slate-300 cursor-pointer select-none ml-2">
            <input
              type="checkbox"
              checked={replyToBot}
              onChange={(e) => setReplyToBot(e.target.checked)}
              className="rounded bg-slate-800 border-slate-700 text-sky-500 cursor-pointer"
            />
            <span className="text-xs">Ответ боту</span>
          </label>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-sm">
            <span className="text-4xl mb-3">💬</span>
            <span className="font-semibold text-slate-300">Сообщений в сессии пока нет</span>
            <span className="text-xs text-slate-500 mt-1">
              Выберите участника, отправьте сообщение или нажмите на один из готовых сценариев ниже!
            </span>
          </div>
        ) : (
          messages.map((m) =>
            m.is_admin_alert ? (
              <div key={m.id} className="w-full my-3 flex flex-col items-center">
                <div className="w-full max-w-[85%] rounded-xl border border-amber-500/50 bg-amber-950/30 p-4 shadow-lg backdrop-blur">
                  <div className="flex items-center justify-between border-b border-amber-500/30 pb-2 mb-2 text-xs">
                    <div className="flex items-center space-x-2 font-bold text-amber-300">
                      <span className="text-base">👑</span>
                      <span>Личное оповещение администратору (ЛС от {botName})</span>
                    </div>
                    <span className="text-[10px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full border border-amber-500/40 font-mono font-bold">
                      TELEGRAM ALERT
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs text-slate-200">
                    <div className="flex items-center space-x-2">
                      <span className="text-slate-400">📍 Чат:</span>
                      <span className="font-mono bg-slate-900/90 px-1.5 py-0.5 rounded text-sky-300">
                        {m.alert_details?.chat_id || 'Dev Test Group'}
                      </span>
                      {m.alert_details?.context_info && (
                        <span className="text-[11px] text-slate-400">({m.alert_details.context_info})</span>
                      )}
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-slate-400">❌ Тип ошибки:</span>
                      <span className="font-mono text-red-400 font-semibold">
                        {m.alert_details?.error_type || 'Error'}
                      </span>
                    </div>
                    <div className="mt-1.5 p-2.5 rounded-lg bg-slate-950/90 border border-slate-800 text-red-300 font-mono text-[11px] whitespace-pre-wrap break-all select-text">
                      {m.alert_details?.error_msg || m.text}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div
                key={m.id}
                className={`flex flex-col ${m.is_bot ? 'items-start' : 'items-end'}`}
              >
                <div className="text-[11px] text-slate-400 mb-1 px-1">{m.user_name}</div>
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm shadow-sm relative ${
                    m.is_bot
                      ? 'bg-slate-800 text-sky-100 border border-slate-700 rounded-tl-sm'
                      : 'bg-sky-600 text-white rounded-tr-sm'
                  }`}
                >
                  <div>{m.text}</div>
                  {m.sensitive && m.sensitive.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-red-400/30 flex items-center space-x-1 text-[11px] text-red-200">
                      <span>🛡️ Обнаружено фильтром:</span>
                      <span className="font-bold uppercase tracking-wider">{m.sensitive.join(', ')}</span>
                    </div>
                  )}
                </div>

                {!m.is_bot && (
                  <div className="mt-1 px-1 text-[10px] max-w-[80%]">
                    {m.error ? (
                      <span className="text-red-400 bg-red-950/40 px-2 py-0.5 rounded border border-red-900 inline-block">
                        ❌ {m.error}
                      </span>
                    ) : m.is_addressed === false ? (
                      <span className="text-slate-400 italic">
                        👁️ {m.trigger_reason || 'Тихое наблюдение: зафиксировано в контексте'}
                      </span>
                    ) : m.is_addressed === true ? (
                      <span className="text-emerald-400">
                        🎯 {m.trigger_reason || 'Бот вызван -> сгенерирован ответ'}
                      </span>
                    ) : null}
                  </div>
                )}
              </div>
            )
          )
        )}
        <div ref={chatEndRef} />
      </div>

      <div className="bg-slate-900/60 border-t border-slate-800 px-6 py-2.5 flex items-center space-x-2 overflow-x-auto text-xs">
        <span className="text-slate-400 flex-shrink-0 font-semibold">Тестовые сценарии:</span>
        <div className="flex space-x-2">
          {presets.map((p, idx) => (
            <button
              key={idx}
              onClick={() => handlePresetClick(p)}
              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-sky-300 rounded-md border border-slate-700 whitespace-nowrap transition cursor-pointer"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSend} className="p-4 bg-slate-900 border-t border-slate-800 flex space-x-3">
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder={`Сообщение от ${currentUser?.name || 'Alice'} (упомяните "${botName}" или включите ответ боту)...`}
          className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 outline-none focus:border-sky-500 transition"
        />
        <button
          type="submit"
          disabled={loading || !inputText.trim()}
          className="px-6 py-2.5 bg-sky-600 hover:bg-sky-500 text-white text-sm font-semibold rounded-xl shadow transition cursor-pointer disabled:opacity-50"
        >
          {loading ? 'Отправка...' : 'Отправить'}
        </button>
      </form>
    </div>
  );
};
