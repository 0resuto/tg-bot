import {
  ChatInfo,
  ContextMessage,
  GraphResponse,
  LogEvent,
  MemoryFact,
  PresetUser,
  SimulatorPreset,
  StatsResponse,
  SystemChecklistResponse,
} from '../types';

export const api = {
  async getHealth(): Promise<SystemChecklistResponse> {
    const res = await fetch('/api/checklist');
    return res.json();
  },

  async getChats(): Promise<ChatInfo[]> {
    const res = await fetch('/api/chats');
    const data = await res.json();
    return data.chats || [];
  },

  async getGraph(chatId?: number): Promise<GraphResponse> {
    const url = chatId ? `/api/graph?chat_id=${chatId}` : '/api/graph';
    const res = await fetch(url);
    return res.json();
  },

  async getMemories(chatId?: number): Promise<MemoryFact[]> {
    const url = chatId ? `/api/memories?chat_id=${chatId}` : '/api/memories';
    const res = await fetch(url);
    const data = await res.json();
    return data.facts || [];
  },

  async forgetFact(description: string, chatId: number): Promise<{ deleted_count: number }> {
    const res = await fetch('/api/forget', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description, chat_id: chatId }),
    });
    return res.json();
  },

  async getContext(chatId?: number): Promise<ContextMessage[]> {
    const url = chatId ? `/api/context?chat_id=${chatId}` : '/api/context';
    const res = await fetch(url);
    const data = await res.json();
    return data.messages || [];
  },

  async getStats(chatId?: number): Promise<StatsResponse> {
    const url = chatId ? `/api/stats?chat_id=${chatId}` : '/api/stats';
    const res = await fetch(url);
    return res.json();
  },

  async getLogs(): Promise<{ current_status: string; last_error?: string | null; logs: LogEvent[] }> {
    const res = await fetch('/api/logs');
    return res.json();
  },

  async getSimulatorPresets(): Promise<{ users: PresetUser[]; presets: SimulatorPreset[] }> {
    const res = await fetch('/api/simulator/presets');
    return res.json();
  },

  async sendSimulatedMessage(payload: {
    user_id: number;
    user_name: string;
    text: string;
    reply_to_bot?: boolean;
  }) {
    const res = await fetch('/api/simulator/send_message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return res.json();
  },
};
