import React, { useEffect, useState } from 'react';

interface AuthModalProps {
  isOpen: boolean;
  onSubmit: (key: string) => void;
  onSkip: () => void;
  error?: string | null;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onSubmit, onSkip, error }) => {
  const [key, setKey] = useState('');

  useEffect(() => {
    if (isOpen) setKey('');
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = key.trim();
    if (trimmed) onSubmit(trimmed);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-sky-500/20 text-sky-400 flex items-center justify-center text-lg font-bold">
            🔑
          </div>
          <div>
            <h3 className="text-base font-bold text-white">Авторизация</h3>
            <p className="text-xs text-slate-400">Введите API-ключ для доступа к панели</p>
          </div>
        </div>

        {error && (
          <div className="p-3 bg-red-950/60 border border-red-800 rounded-lg text-xs text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="password"
            autoFocus
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="WEB_API_KEY"
            className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 outline-none focus:border-sky-500 transition font-mono"
          />
          <div className="flex space-x-2">
            <button
              type="button"
              onClick={onSkip}
              className="flex-1 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-sm font-medium border border-slate-700 transition cursor-pointer"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={!key.trim()}
              className="flex-1 py-2.5 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-sm font-semibold transition cursor-pointer disabled:opacity-50"
            >
              Подключить
            </button>
          </div>
        </form>

        <p className="text-[11px] text-slate-500 text-center">
          Ключ сохраняется в localStorage браузера
        </p>
      </div>
    </div>
  );
};
