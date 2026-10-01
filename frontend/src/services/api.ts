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

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const res = await fetch(input, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
    throw new ApiError(res.status, body.error || body.message || `HTTP ${res.status}`);
  }
  return res;
}

export const api = {
  async getHealth(): Promise<SystemChecklistResponse> {
    const res = await request('/api/health');
    return res.json();
  },
  async getChats(): Promise<ChatInfo[]> {
    const res = await request('/api/chats');
    const data = await res.json();
    return data.chats || [];
  },
  async getGraph(chatId: number): Promise<GraphResponse> {
    const res = await request(`/api/graph?chat_id=${chatId}`);
    return res.json();
  },
  async getMemories(chatId: number): Promise<MemoryFact[]> {
    const res = await request(`/api/memories?chat_id=${chatId}`);
    const data = await res.json();
    return data.facts || [];
  },
  async getContext(chatId?: number): Promise<ContextMessage[]> {
    const url = chatId ? `/api/context?chat_id=${chatId}` : '/api/context';
    const res = await request(url);
    const data = await res.json();
    return data.messages || [];
  },
  async getStats(chatId?: number): Promise<StatsResponse> {
    const url = chatId ? `/api/stats?chat_id=${chatId}` : '/api/stats';
    const res = await request(url);
    return res.json();
  },
  async getLogs(): Promise<{
    current_status: string;
    last_error?: string | null;
    logs: LogEvent[];
  }> {
    const res = await request('/api/logs');
    return res.json();
  },
  async getSimulatorPresets(): Promise<{ users: PresetUser[]; presets: SimulatorPreset[] }> {
    const res = await request('/api/simulator/presets');
    return res.json();
  },
  async sendSimulatedMessage(payload: {
    user_id: number;
    user_name: string;
    text: string;
    reply_to_bot?: boolean;
  }) {
    const res = await request('/api/simulator/send_message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return res.json();
  },
};
