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
