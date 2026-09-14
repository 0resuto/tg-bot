import React, { useState } from 'react';
import { StatsResponse } from '../types';

interface AdminViewProps {
  stats: StatsResponse | null;
  selectedChatId: number | null;
  onForgetFact: (description: string) => Promise<number>;
}

export const AdminView: React.FC<AdminViewProps> = React.memo(({
  stats,
  selectedChatId,
  onForgetFact,
}) => {
  const [forgetText, setForgetText] = useState('');
  const [forgetting, setForgetting] = useState(false);
  const [forgetResult, setForgetResult] = useState<string | null>(null);

  const [testText, setTestText] = useState('');
  const [detectedCategories, setDetectedCategories] = useState<string[] | null>(null);

  const handleForgetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!forgetText.trim()) return;
    setForgetting(true);
    setForgetResult(null);
    try {
      const deleted = await onForgetFact(forgetText.trim());
      setForgetResult(`Успешно удалено фактов: ${deleted}`);
      setForgetText('');
    } catch (err: any) {
      setForgetResult(`Ошибка: ${err.message || String(err)}`);
    } finally {
      setForgetting(false);
    }
  };

  // Local client regex simulator for sensitive topics
  const handleTestFilter = (text: string) => {
    setTestText(text);
    if (!text.trim()) {
      setDetectedCategories(null);
      return;
    }
    const categories: string[] = [];
    if (/medical|diagnosis|prescription|disease|illness|symptom|болезнь|диагноз|рецепт|симптом|больница|лекарство/i.test(text)) {
      categories.push('HEALTH');
    }
    if (/salary|income|debt|credit card|bank account|\$\d+|\d+\s*руб|зарплата|доход|долг|кредитка|счет|банк/i.test(text)) {
      categories.push('FINANCE');
    }
    if (/password|api key|token|secret key|pin code|пароль|токен|секретный ключ|пин код/i.test(text)) {
      categories.push('CREDENTIALS');
    }
    if (/arrested|court|lawsuit|immigration|deportation|criminal|арест|суд|иск|иммиграция|депортация|преступление/i.test(text)) {
      categories.push('LEGAL');
    }
    if (/porn|sex|порно|секс|эротика/i.test(text)) {
      categories.push('SEXUAL');
    }
    if (/party membership|voting for|republican|democrat|партия|голосовать|выборы|политика/i.test(text)) {
      categories.push('POLITICAL');
    }
    setDetectedCategories(categories);
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto overflow-y-auto">
      <div>
        <h2 className="text-xl font-bold text-white tracking-wide">Администрирование и безопасность</h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Инструменты управления памятью, конфиденциальностью и ресурсами
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Memory Scrubbing Tool */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <span>🧹</span>
              <span>Очистка фактов из графа (/forget_fact)</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Находит и безвозвратно удаляет факты в Neo4j, соответствующие описанию
              {selectedChatId ? ` для чата ${selectedChatId}` : ''}.
            </p>
          </div>

          <form onSubmit={handleForgetSubmit} className="space-y-3">
            <input
              type="text"
              value={forgetText}
              onChange={(e) => setForgetText(e.target.value)}
              placeholder="Например: 'любит кофе' или 'Алиса уехала в Рим'"
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2.5 text-xs text-slate-100 outline-none focus:border-red-500 transition"
            />
            <button
              type="submit"
              disabled={forgetting || !forgetText.trim()}
              className="w-full py-2 px-4 bg-red-950/80 hover:bg-red-900 text-red-200 border border-red-800 rounded-lg text-xs font-semibold transition cursor-pointer disabled:opacity-50"
            >
              {forgetting ? 'Очистка памяти...' : 'Удалить факт из графа'}
            </button>
          </form>

          {forgetResult && (
            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs font-mono text-sky-400">
              {forgetResult}
            </div>
          )}
        </div>

        {/* Sensitive Content Tester */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <span>🛡️</span>
              <span>Тестирование фильтра чувствительных тем</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Проверьте, распознает ли SensitiveFilter конфиденциальные данные (финансы, пароли, здоровье)
            </p>
          </div>

          <textarea
            rows={3}
            value={testText}
            onChange={(e) => handleTestFilter(e.target.value)}
            placeholder="Введите текст (например: 'Моя зарплата 150000 руб, а пароль secret123')..."
            className="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-xs text-slate-100 outline-none focus:border-sky-500 transition"
          />

          {detectedCategories !== null && (
            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs space-y-2">
              <div className="text-slate-400 font-semibold">Результат сканирования:</div>
              {detectedCategories.length === 0 ? (
                <div className="text-emerald-400 font-medium">
                  ✅ Конфиденциальных категорий не обнаружено (разрешено для памяти)
                </div>
              ) : (
                <div className="space-y-1.5">
                  <div className="text-red-400 font-medium">
                    ⚠️ Обнаружены категории: {detectedCategories.join(', ')}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    {detectedCategories.includes('CREDENTIALS')
                      ? '🛑 Сообщение будет полностью пропущено (никогда не попадает в долговременную память).'
                      : '✂️ Текст будет автоматически отредактирован ([REDACTED]) перед отправкой в LLM.'}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Token Usage Stats Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center space-x-2">
            <span>📊</span>
            <span>Статистика потребления токенов</span>
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Учет расходов токенов по операциям извлечения фактов и генерации ответов
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
            <div className="text-slate-400">Сегодня (Today):</div>
            <div className="text-xl font-bold text-emerald-400 mt-1 font-mono">
              {(stats?.token_stats?.today_tokens || 0).toLocaleString()}
            </div>
          </div>
          <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
            <div className="text-slate-400">За 30 дней (Month):</div>
            <div className="text-xl font-bold text-sky-400 mt-1 font-mono">
              {(stats?.token_stats?.month_tokens || 0).toLocaleString()}
            </div>
          </div>
          <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
            <div className="text-slate-400">Модель ответов:</div>
            <div className="text-sm font-bold text-purple-400 mt-1 font-mono truncate">
              {stats?.llm_model || 'OpenAI'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});
