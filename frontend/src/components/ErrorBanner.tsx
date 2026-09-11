import React from 'react';

interface ErrorBannerProps {
  title: string;
  error: string;
  details?: string | null;
  onDismiss: () => void;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  title,
  error,
  details,
  onDismiss,
}) => {
  return (
    <div className="bg-red-950/90 border-b border-red-800 px-6 py-3 text-xs text-red-200 flex items-start justify-between shadow-lg">
      <div className="flex-1 pr-4">
        <div className="font-bold flex items-center space-x-1.5 text-red-300 text-sm">
          <span>⚠️</span>
          <span>{title}</span>
        </div>
        <div className="mt-1 font-mono text-xs text-red-200 whitespace-pre-wrap">{error}</div>
        {details && (
          <details className="mt-2 text-[11px] text-slate-400">
            <summary className="cursor-pointer hover:underline text-red-400 font-semibold">
              Показать Traceback исключения
            </summary>
            <pre className="mt-1.5 p-3 bg-black/80 rounded-lg text-[10px] text-red-300 overflow-x-auto whitespace-pre-wrap font-mono border border-red-900/50">
              {details}
            </pre>
          </details>
        )}
      </div>
      <button
        onClick={onDismiss}
        className="text-red-400 hover:text-white text-lg font-bold px-2 py-1 rounded transition"
      >
        ✕
      </button>
    </div>
  );
};
