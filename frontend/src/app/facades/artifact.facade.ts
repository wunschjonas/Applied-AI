import { Injectable, signal } from '@angular/core';
import { toAbsoluteApiUrl } from '../core/api.config';
import { GeneratedArtifacts } from '../models/artifact.model';
import { PostPreview } from '../models/post.model';

/**
 * Holds the current post artifacts so all three agent pages and the preview
 * page show the same state, no matter which agent produced it last.
 */
@Injectable({
  providedIn: 'root',
})
export class ArtifactFacade {
  private _generatedText = signal<string | null>(null);
  public generatedText = this._generatedText.asReadonly();

  private _hashtags = signal<string[]>([]);
  public hashtags = this._hashtags.asReadonly();

  private _imagePrompt = signal<string | null>(null);
  public imagePrompt = this._imagePrompt.asReadonly();

  private _imageUrl = signal<string | null>(null);
  public imageUrl = this._imageUrl.asReadonly();

  private _generationMode = signal<string | null>(null);
  public generationMode = this._generationMode.asReadonly();

  /** Merge a chat response so a text-only answer keeps the existing image and vice versa. */
  public applyArtifacts(artifacts: GeneratedArtifacts | undefined | null): void {
    if (!artifacts) return;

    const text = artifacts.text;
    if (text?.generated_text) {
      this._generatedText.set(text.generated_text);
      this._hashtags.set(text.hashtags ?? []);
    }

    const image = artifacts.image;
    if (image?.image_prompt) {
      this._imagePrompt.set(image.image_prompt);
    }
    if (image?.image_url) {
      // Cache buster: the file name stays {post_id}.png across regenerations.
      this._imageUrl.set(`${toAbsoluteApiUrl(image.image_url)}?t=${Date.now()}`);
    }
    if (image?.generation_mode) {
      this._generationMode.set(image.generation_mode);
    }
  }

  /** Restore the stored state of a post, e.g. after a reload or when switching posts. */
  public applyPreview(preview: PostPreview | null | undefined): void {
    this._generatedText.set(preview?.generated_text || null);
    this._hashtags.set(preview?.hashtags ?? []);
    this._imagePrompt.set(preview?.image_prompt_optional ?? null);
    this._imageUrl.set(
      preview?.image_url ? `${toAbsoluteApiUrl(preview.image_url)}?t=${Date.now()}` : null,
    );
    this._generationMode.set(null);
  }

  public reset(): void {
    this._generatedText.set(null);
    this._hashtags.set([]);
    this._imagePrompt.set(null);
    this._imageUrl.set(null);
    this._generationMode.set(null);
  }
}
