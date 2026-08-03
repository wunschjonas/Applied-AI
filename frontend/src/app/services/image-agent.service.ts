import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { API_BASE_URL } from '../core/api.config';
import { AgentChatHistory } from '../models/chat.model';
import { GeneratedArtifacts } from '../models/artifact.model';

export interface ChatResponse {
  chat_id: string;
  assistant_message: string;
  generated_artifacts?: GeneratedArtifacts;
  trace_id?: string;
}

@Injectable({
  providedIn: 'root',
})
export class ImageAgentService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = API_BASE_URL;

  public getChatHistory(postId: string): Observable<AgentChatHistory> {
    return this.http.get<AgentChatHistory>(
      `${this.baseUrl}/api/agents/image/chats/${postId}::image_agent`,
    );
  }

  public chat(
    message: string,
    postId: string,
    sourceImage?: File | null,
    strength = 0.7,
  ): Observable<ChatResponse> {
    const endpoint = `${this.baseUrl}/api/agents/image/chat`;
    const form = new FormData();
    form.append('message', message);
    form.append('post_id', postId);
    form.append('strength', String(strength));
    if (sourceImage) {
      form.append('source_image', sourceImage, sourceImage.name);
    }
    console.log('[ImageAgent] POST', endpoint, {
      message,
      post_id: postId,
      has_source_image: Boolean(sourceImage),
      strength,
    });
    return this.http.post<ChatResponse>(endpoint, form).pipe(
      tap({
        next: (response) => console.log('[ImageAgent] Response:', response),
        error: (err) => console.error('[ImageAgent] Error:', err),
      }),
    );
  }
}
