export interface TextArtifact {
  generated_text?: string;
  hashtags?: string[];
  platform?: string | null;
}

export interface ImageArtifact {
  image_prompt?: string;
  suggested_style?: string;
  image_url?: string | null;
  image_filename?: string | null;
  image_error?: string | null;
}

export interface GeneratedArtifacts {
  text?: TextArtifact;
  image?: ImageArtifact;
}
