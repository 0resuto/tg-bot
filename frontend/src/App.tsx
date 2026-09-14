import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, setAuthPromptCallback } from './services/api';
import {
  ChatInfo,
  ContextMessage,
  GraphResponse,
  LogEvent,
  MemoryFact,
  PresetUser,
  SimulatedMessage,
  SimulatorPreset,
  StatsResponse,
  SystemChecklistResponse,
} from './types';
import { Header } from './components/Header';
import { Sidebar, TabType } from './components/Sidebar';
import { ErrorBanner } from './components/ErrorBanner';
import { AuthModal } from './components/AuthModal';
import { OverviewView } from './views/OverviewView';
import { KnowledgeGraphView } from './views/KnowledgeGraphView';
import { MemoriesView } from './views/MemoriesView';
import { ContextView } from './views/ContextView';
import { AdminView } from './views/AdminView';
import { LogsView } from './views/LogsView';
import { SimulatorView } from './views/SimulatorView';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>(() => {
    return (localStorage.getItem('dashboard_active_tab') as TabType) || 'overview';
  });

  const [chats, setChats] = useState<ChatInfo[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<number | null>(null);
  const selectedChatIdRef = useRef(selectedChatId);
  selectedChatIdRef.current = selectedChatId;

  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [healthData, setHealthData] = useState<SystemChecklistResponse | null>(null);
  const [isRefreshingHealth, setIsRefreshingHealth] = useState(false);

  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);

  const [memories, setMemories] = useState<MemoryFact[]>([]);
  const [contextMessages, setContextMessages] = useState<ContextMessage[]>([]);
  const [logs, setLogs] = useState<LogEvent[]>([]);

  const [simulatorUsers, setSimulatorUsers] = useState<PresetUser[]>([]);
  const [simulatorPresets, setSimulatorPresets] = useState<SimulatorPreset[]>([]);
  const [simulatedMessages, setSimulatedMessages] = useState<SimulatedMessage[]>([]);
  const [sendingMessage, setSendingMessage] = useState(false);
  const msgIdCounter = useRef(0);

  const [errorBanner, setErrorBanner] = useState<{ title: string; error: string; details?: string | null } | null>(null);
  const [pollingError, setPollingError] = useState<string | null>(null);

  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalError, setAuthModalError] = useState<string | null>(null);
  const authResolveRef = useRef<((key: string | null) => void) | null>(null);

  useEffect(() => {
    setAuthPromptCallback((resolve) => {
      authResolveRef.current = resolve;
      setAuthModalOpen(true);
      setAuthModalError(null);
    });
    return () => setAuthPromptCallback(null);
  }, []);

  const handleAuthSubmit = (key: string) => {
    setAuthModalOpen(false);
    setAuthModalError(null);
    authResolveRef.current?.(key);
    authResolveRef.current = null;
  };

  const handleAuthSkip = () => {
    setAuthModalOpen(false);
    setAuthModalError(null);
    authResolveRef.current?.(null);
    authResolveRef.current = null;
  };

  const handleSelectTab = useCallback((tab: TabType) => {
    setActiveTab(tab);
    localStorage.setItem('dashboard_active_tab', tab);
  }, []);

  const presetsLoadedRef = useRef(false);

  const refreshAllData = useCallback(async () => {
    const chatId = selectedChatIdRef.current;
    try {
      const [statsRes, memoriesRes, contextRes, logsRes, chatsRes] = await Promise.all([
        api.getStats(chatId ?? undefined),
        api.getMemories(chatId ?? undefined),
        api.getContext(chatId ?? undefined),
        api.getLogs(),
        api.getChats(),
      ]);

      setStats(statsRes);
      setMemories(memoriesRes);
      setContextMessages(contextRes);
      setLogs(logsRes.logs || []);

      if (chatsRes && chatsRes.length > 0) {
        setChats(chatsRes);
        setSelectedChatId((prev) => (prev === null ? chatsRes[0].chat_id : prev));
      }

      if (statsRes.enable_simulator && !presetsLoadedRef.current) {
        presetsLoadedRef.current = true;
        api.getSimulatorPresets().then((p) => {
          setSimulatorUsers(p.users || []);
          setSimulatorPresets(p.presets || []);
        }).catch((err) => {
          console.error('Failed to load simulator presets', err);
        });
      }

      setPollingError(null);
    } catch (err: any) {
      console.error('Refresh cycle failed', err);
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setPollingError(null);
      } else {
        setPollingError(err.message || 'Ошибка соединения с сервером');
      }
    }
  }, []);

  useEffect(() => {
    refreshAllData();
    const interval = setInterval(refreshAllData, 5000);
    return () => clearInterval(interval);
  }, [selectedChatId, refreshAllData]);

  const loadGraph = useCallback(async () => {
    setLoadingGraph(true);
    try {
      const data = await api.getGraph(selectedChatIdRef.current ?? undefined);
      setGraphData(data);
    } catch (err: any) {
      console.error('Failed to load graph', err);
    } finally {
      setLoadingGraph(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'graph') {
      loadGraph();
    }
  }, [activeTab, loadGraph]);

  useEffect(() => {
    if (activeTab === 'graph') {
      loadGraph();
    }
  }, [selectedChatId, activeTab, loadGraph]);

  const handleRefreshHealth = useCallback(async () => {
    setIsRefreshingHealth(true);
    try {
      const data = await api.getHealth();
      setHealthData(data);
      refreshAllData();
    } catch (err: any) {
      setErrorBanner({
        title: 'Сбой проверки сервисов',
        error: err.message || String(err),
      });
    } finally {
      setIsRefreshingHealth(false);
    }
  }, [refreshAllData]);

  const handleForgetFact = useCallback(async (description: string) => {
    if (!selectedChatIdRef.current) return 0;
    const res = await api.forgetFact(description, selectedChatIdRef.current);
    refreshAllData();
    loadGraph();
    return res.deleted_count || 0;
  }, [refreshAllData, loadGraph]);

  const handleSendSimulatedMessage = useCallback(async (user: PresetUser, text: string, replyToBot: boolean) => {
    setSendingMessage(true);
    const optimisticId = `opt-${++msgIdCounter.current}`;
    setSimulatedMessages((prev) => [
      ...prev,
      {
        id: optimisticId,
        user_name: user.name,
        text,
        timestamp: new Date().toISOString(),
      },
    ]);

    try {
      const data = await api.sendSimulatedMessage({
        user_id: user.id,
        user_name: user.name,
        text,
        reply_to_bot: replyToBot,
      });

      if (!data.success && data.error) {
        setErrorBanner({
          title: 'Ошибка выполнения пайплайна симулятора',
          error: data.error,
          details: data.error_details,
        });
        setSimulatedMessages((prev) =>
          prev.map((m) =>
            m.id === optimisticId ? { ...m, error: data.error, trigger_reason: data.trigger_reason } : m
          )
        );
      } else {
        setSimulatedMessages((prev) => {
          const updated = prev.map((m) =>
            m.id === optimisticId
              ? {
                  ...m,
                  sensitive: data.sensitive_categories,
                  is_addressed: data.is_addressed,
                  trigger_reason: data.trigger_reason,
                }
              : m
          );

          const newMsgs: SimulatedMessage[] = [];

          if (data.bot_reply) {
            newMsgs.push({
              id: `bot-${++msgIdCounter.current}`,
              user_name: `${data.bot_names ? data.bot_names[0] : 'Bot'} (Bot)`,
              text: data.bot_reply,
              timestamp: new Date().toISOString(),
              is_bot: true,
            });
          }

          if (data.admin_alerts && Array.isArray(data.admin_alerts) && data.admin_alerts.length > 0) {
            for (const alert of data.admin_alerts) {
              newMsgs.push({
                id: `alert-${++msgIdCounter.current}`,
                user_name: '👑 Оповещение администратору (Telegram Alert)',
                text: alert.error_msg || alert.formatted_text || 'Ошибка при генерации ответа',
                timestamp: alert.timestamp || new Date().toISOString(),
                is_admin_alert: true,
                alert_details: {
                  chat_id: alert.chat_id,
                  error_type: alert.error_type,
                  error_msg: alert.error_msg,
                  context_info: alert.context_info,
                },
              });
            }
          }

          return newMsgs.length > 0 ? [...updated, ...newMsgs] : updated;
        });
      }
      refreshAllData();
      loadGraph();
    } catch (err: any) {
      setErrorBanner({
        title: 'Ошибка сети',
        error: err.message || 'Не удалось отправить сообщение серверу.',
      });
    } finally {
      setSendingMessage(false);
    }
  }, [refreshAllData, loadGraph]);

  const botName = stats?.bot_names?.[0] || 'Bot';
  const checklist = healthData?.items || stats?.checklist || [];

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 font-sans">
      <AuthModal isOpen={authModalOpen} onSubmit={handleAuthSubmit} onSkip={handleAuthSkip} error={authModalError} />

      <Header
        stats={stats}
        botStatus={stats?.all_ready ? 'ready' : 'error'}
        onRefresh={handleRefreshHealth}
        isRefreshing={isRefreshingHealth}
        pollingError={pollingError}
      />

      {errorBanner && (
        <ErrorBanner
          title={errorBanner.title}
          error={errorBanner.error}
          details={errorBanner.details}
          onDismiss={() => setErrorBanner(null)}
        />
      )}

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          activeTab={activeTab}
          onSelectTab={handleSelectTab}
          chats={chats}
          selectedChatId={selectedChatId}
          onSelectChat={setSelectedChatId}
          enableSimulator={stats?.enable_simulator ?? false}
          factsCount={memories.length}
          messagesCount={contextMessages.length}
        />

        <main className="flex-1 overflow-hidden bg-slate-950 flex flex-col">
          {activeTab === 'overview' && (
            <OverviewView
              stats={stats}
              checklist={checklist}
              factsCount={stats?.memory_stats?.total_episodes ?? memories.length}
              graphNodesCount={stats?.memory_stats?.total_entities ?? 0}
              graphEdgesCount={stats?.memory_stats?.total_relations ?? 0}
              contextMessagesCount={contextMessages.length}
              onNavigate={handleSelectTab}
              onRefreshHealth={handleRefreshHealth}
              isRefreshingHealth={isRefreshingHealth}
            />
          )}

          {activeTab === 'graph' && (
            <KnowledgeGraphView
              graphData={graphData}
              loadingGraph={loadingGraph}
              onRefreshGraph={loadGraph}
            />
          )}

          {activeTab === 'memories' && (
            <MemoriesView
              memories={memories}
              onForgetFact={handleForgetFact}
              onRefresh={refreshAllData}
            />
          )}

          {activeTab === 'context' && (
            <ContextView
              contextMessages={contextMessages}
              onRefresh={refreshAllData}
            />
          )}

          {activeTab === 'admin' && (
            <AdminView
              stats={stats}
              selectedChatId={selectedChatId}
              onForgetFact={handleForgetFact}
            />
          )}

          {activeTab === 'logs' && (
            <LogsView logs={logs} onRefresh={refreshAllData} />
          )}

          {activeTab === 'simulator' && (
            <SimulatorView
              users={simulatorUsers}
              presets={simulatorPresets}
              messages={simulatedMessages}
              onSendMessage={handleSendSimulatedMessage}
              loading={sendingMessage}
              botName={botName}
            />
          )}
        </main>
      </div>
    </div>
  );
};
