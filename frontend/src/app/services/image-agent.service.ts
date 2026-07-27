import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { AgentChatHistory } from '../models/chat.model';

export interface ChatResponse {
  message: string;
}

@Injectable({
  providedIn: 'root',
})
export class ImageAgentService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:8080';

  public getChatHistory(postId: string): Observable<AgentChatHistory> {
    return this.http.get<AgentChatHistory>(
      `${this.baseUrl}/api/agents/image/chats/${postId}::image_agent`,
    );
  }

  public chat(message: string, postId: string): Observable<ChatResponse> {
    const endpoint = `${this.baseUrl}/api/agents/image/chat`;
    const payload = { message, post_id: postId };
    console.log('[ImageAgent] POST', endpoint, payload);
    return this.http.post<ChatResponse>(endpoint, payload).pipe(
      tap({
        next: (response) => console.log('[ImageAgent] Response:', response),
        error: (err) => console.error('[ImageAgent] Error:', err),
      }),
    );
  }
}
