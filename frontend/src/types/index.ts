export interface Brand {
  id: string;
  user_id: string;
  name: string;
  industry: string | null;
  overview: string | null;
  tone: string;
  target_audience: string | null;
  products_services: string | null;
  logo_path: string | null;
  colors: string[];
  product_images: string[];
  style_reference_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BrandCreate {
  name: string;
  industry?: string;
  overview?: string;
  tone: string;
  target_audience?: string;
  products_services?: string;
  logo_path?: string;
  colors?: string[];
  product_images?: string[];
  style_reference_url?: string;
}

export type BrandUpdate = Partial<BrandCreate>;

export interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  requires_product_images: boolean;
}

export interface Session {
  id: string;
  user_id: string;
  brand_id: string;
  agent_type: string;
  thread_id: string;
  status: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionCreate {
  brand_id: string;
  agent_type: string;
}

export interface ChatRequest {
  message: string;
  attachments?: string[];
}

export interface Choice {
  id: string;
  label: string;
  description?: string;
}

export interface InteractiveResponse {
  type: string;
  message: string;
  choices: Choice[];
  has_choices: boolean;
  choice_type: 'single_select' | 'multi_select' | 'confirmation' | 'menu';
  allow_free_input: boolean;
  input_placeholder: string;
  media?: {
    image_path?: string;
    video_path?: string;
  };
}

export type SSEEvent =
  | { type: 'text'; content: string; partial: boolean }
  | { type: 'tool_start'; tool: string; message: string }
  | { type: 'tool_end'; tool: string }
  | { type: 'interactive'; content: InteractiveResponse }
  | { type: 'status'; message: string }
  | { type: 'error'; content: string }
  | { type: 'done' };

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'error' | 'status';
  content: string;
  interactive?: InteractiveResponse;
  toolName?: string;
  toolActive?: boolean;
  imageUrl?: string;
}

export interface LogoUploadResponse {
  logo_path: string;
  url: string;
  colors: string[];
}

export interface ProductImageUploadResponse {
  image_path: string;
  url: string;
}

// --- Usage Monitoring ---
export interface UsageSummaryItem {
  model_name: string;
  action_type: string;
  total_calls: number;
  successful_calls: number;
  failed_calls: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cost_usd: number;
  total_video_seconds: number;
}

export interface UsageSummaryResponse {
  items: UsageSummaryItem[];
  total_cost_usd: number;
}

export interface UsageLogItem {
  id: string;
  session_id: string | null;
  action_type: string;
  model_name: string;
  tool_name: string | null;
  status: string;
  cost_usd: number;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  unit_count: number;
  video_duration_seconds: number | null;
  error_message: string | null;
  created_at: string | null;
}

export interface UsageHistoryResponse {
  items: UsageLogItem[];
  total: number;
  limit: number;
  offset: number;
}

// --- Content Calendar ---
export interface CalendarSlot {
  id: string;
  plan_id: string;
  slot_date: string; // ISO date
  event_name: string | null;
  event_type: string | null; // festival, trending, brand, regular
  post_idea: string | null;
  post_type: string;
  status: string; // suggested, approved, generating, generated, skipped
  session_id: string | null;
  generated_image: string | null;
  caption: string | null;
  hashtags: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CalendarPlan {
  id: string;
  user_id: string;
  brand_id: string;
  year: number;
  month: number;
  status: string; // draft, active, archived
  slots: CalendarSlot[];
  created_at: string;
  updated_at: string;
}

export interface CalendarSlotUpdate {
  event_name?: string;
  event_type?: string;
  post_idea?: string;
  post_type?: string;
  status?: string;
}

export interface CreateContentResponse {
  session_id: string;
  slot_id: string;
  agent_type: string;
  post_idea: string;
}
