import {
  ChatInfo, ContextMessage, GraphResponse, LogEvent, MemoryFact,
  PresetUser, SimulatorPreset, StatsResponse, SystemChecklistResponse,
} from '../types';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

let authPromptCallback: ((resolve: (key: string | null) => void) => void) | null = null;

export function setAuthPromptCallback(cb: typeof authPromptCallback) {
  authPromptCallback = cb;
}

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('web_api_key');
  const headers: Record<string, string> = {};
  if (token) { headers['X-API-Key'] = token; }
  return headers;
}

function promptForApiKey(): Promise<string | null> {
  if (authPromptCallback) {
    return new Promise<string | null>((resolve) => authPromptCallback!(resolve));
  }
  const key = window.prompt('Панель управления требует API-ключ. Пожалуйста, введите WEB_API_KEY:');
  return Promise.resolve(key ? key.trim() : null);
}

async function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const headers = { ...getAuthHeaders(), ...(init?.headers || {}) };
  let res = await fetch(input, { ...init, headers });

  if (res.status === 401) {
    const key = await promptForApiKey();
    if (key) {
      localStorage.setItem('web_api_key', key);
      const retryHeaders = { ...headers, 'X-API-Key': key };
      res = await fetch(input, { ...init, headers: retryHeaders });
    }
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
    throw new ApiError(res.status, body.error || body.message || `HTTP ${res.status}`);
  }

  return res;
}

export const api = {
  getApiKey(): string { return localStorage.getItem('web_api_key') || ''; },
  setApiKey(key: string): void {
    if (key.trim()) { localStorage.setItem('web_api_key', key.trim()); }
    else { localStorage.removeItem('web_api_key'); }
  },
  async getHealth(): Promise<SystemChecklistResponse> {
    const res = await authFetch('/api/checklist'); return res.json();
  },
  async getChats(): Promise<ChatInfo[]> {
    const res = await authFetch('/api/chats');
    const data = await res.json(); return data.chats || [];
  },
  async getGraph(chatId?: number): Promise<GraphResponse> {
    const url = chatId ? `/api/graph?chat_id=${chatId}` : '/api/graph';
    const res = await authFetch(url); return res.json();
  },
  async getMemories(chatId?: number): Promise<MemoryFact[]> {
    const url = chatId ? `/api/memories?chat_id=${chatId}` : '/api/memories';
    const res = await authFetch(url);
    const data = await res.json(); return data.facts || [];
  },
  async forgetFact(description: string, chatId: number): Promise<{ deleted_count: number }> {
    const res = await authFetch('/api/forget', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description, chat_id: chatId }),
    }); return res.json();
  },
  async getContext(chatId?: number): Promise<ContextMessage[]> {
    const url = chatId ? `/api/context?chat_id=${chatId}` : '/api/context';
    const res = await authFetch(url);
    const data = await res.json(); return data.messages || [];
  },
  async getStats(chatId?: number): Promise<StatsResponse> {
    const url = chatId ? `/api/stats?chat_id=${chatId}` : '/api/stats';
    const res = await authFetch(url); return res.json();
  },
  async getLogs(): Promise<{ current_status: string; last_error?: string | null; logs: LogEvent[] }> {
    const res = await authFetch('/api/logs'); return res.json();
  },
  async getSimulatorPresets(): Promise<{ users: PresetUser[]; presets: SimulatorPreset[] }> {
    const res = await authFetch('/api/simulator/presets'); return res.json();
  },
  async sendSimulatedMessage(payload: {
    user_id: number; user_name: string; text: string; reply_to_bot?: boolean;
  }) {
    const res = await authFetch('/api/simulator/send_message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }); return res.json();
  },
};
