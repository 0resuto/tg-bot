export interface ChecklistItem {
  id: string;
  name: string;
  target: string;
  status: 'ok' | 'error' | 'unknown';
  message: string;
  error?: string | null;
}

export interface SystemChecklistResponse {
  all_ready: boolean;
  items: ChecklistItem[];
  checked_at: string;
}

export interface ChatInfo {
  chat_id: number;
  title: string;
  is_active: boolean;
  created_at: string | null;
  is_simulator?: boolean;
}

export interface StatsResponse {
  all_ready: boolean;
  checklist: ChecklistItem[];
  llm_model: string;
  memory_backend: string;
  bot_names: string[];
  enable_simulator: boolean;
  memory_stats?: {
    status?: string;
    facts?: number;
    entities?: number;
    relations?: number;
    tracked_members?: number;
    last_ingestion?: string;
    [key: string]: any;
  };
  token_stats?: {
    today_tokens?: number;
    month_tokens?: number;
    extraction_tokens?: number;
    response_tokens?: number;
    [key: string]: any;
  };
}

export interface GraphNode {
  id: string;
  label: string;
  raw_label: string;
  icon: string;
  full_name: string;
  labels: string[];
  group: string;
  color: { background: string; border: string };
  shape: string;
  size: number;
  font: { color: string; face: string };
  properties: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  from: string;
  to: string;
  label: string;
  type: string;
  full_fact: string;
  properties: Record<string, any>;
  arrows: string;
  color: { color: string; highlight: string; hover: string };
  font: { size: number; color: string; background: string };
}

export interface GraphResponse {
  success: boolean;
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    nodes_count: number;
    edges_count: number;
  };
  error?: string;
}

export interface SelectedGraphItem {
  type: 'node' | 'edge';
  data: any;
}

export interface MemoryFact {
  subject: string;
  fact_text: string;
  created_at: string | null;
}

export interface ContextMessage {
  message_id: number;
  user_id: number;
  display_name: string;
  text: string;
  timestamp: string;
}

export interface PresetUser {
  id: number;
  name: string;
  avatar: string;
  role: string;
}

export interface SimulatorPreset {
  label: string;
  text: string;
  user: string;
}

export interface SimulatedMessage {
  id: number;
  user_name: string;
  text: string;
  timestamp: string;
  is_bot?: boolean;
  sensitive?: string[];
  is_addressed?: boolean;
  trigger_reason?: string;
  error?: string;
  is_admin_alert?: boolean;
  alert_details?: {
    chat_id?: number;
    error_type?: string;
    error_msg?: string;
    context_info?: string;
  };
}

export interface LogEvent {
  id: number;
  timestamp: string;
  user_name?: string;
  text?: string;
  status: string;
  error?: string;
  traceback?: string;
  is_addressed?: boolean;
  bot_reply?: string;
  [key: string]: any;
}
