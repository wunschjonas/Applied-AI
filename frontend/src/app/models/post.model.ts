export interface InitPostResponse {
  post_id: string;
  title: string;
  created_at?: string;
  welcome_message?: string;
  missing_fields?: string[];
}

export type PostStatus = 'draft' | 'processing' | 'preview_ready' | 'error';

export interface PostPreview {
  generated_text: string;
  post_structure: Record<string, unknown>;
  hashtags: string[];
  image_prompt_optional?: string | null;
  image_url?: string | null;
  image_filename?: string | null;
}

export interface Post {
  id: string;
  title: string;
  status: PostStatus;
  topic?: string | null;
  platform?: string | null;
  target_audience?: string | null;
  tone_of_voice?: string | null;
  text_context?: string | null;
  text_length?: string | null;
  image_context?: string | null;
  image_style?: string | null;
  preview?: PostPreview | null;
  missing_fields?: string[];
}
