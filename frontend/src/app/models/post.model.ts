export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface CreatePostRequest {
  title: string;
  topic: string;
  platform: string;
  target_audience: string;
  tone_of_voice: string;
  goal: string;
  additional_context?: string;
}

export interface UpdatePostRequest {
  title?: string;
  topic?: string;
  platform?: string;
  target_audience?: string;
  tone_of_voice?: string;
  goal?: string;
  additional_context?: string;
}

export interface Post {
  id: string;
  title: string;
  topic: string;
  platform: string;
  target_audience: string;
  tone_of_voice: string;
  goal: string;
  additional_context?: string;
}

export interface PostPreview {
  post_id: string;
  generated_post: string;
  post_structure?: string;
  hashtags?: string[];
  agent_trace?: AgentTraceStep[];
}

export interface AgentTraceStep {
  timestamp: string;
  thought: string;
  action: string;
  observation: string;
}
