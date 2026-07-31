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
export class TextAgentService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = API_BASE_URL;

  public getChatHistory(postId: string): Observable<AgentChatHistory> {
    return this.http.get<AgentChatHistory>(
      `${this.baseUrl}/api/agents/text/chats/${postId}::text_agent`,
    );
  }

  public chat(message: string, postId: string): Observable<ChatResponse> {
    const endpoint = `${this.baseUrl}/api/agents/text/chat`;
    const payload = { message, post_id: postId };
    console.log('[TextAgent] POST', endpoint, payload);
    return this.http.post<ChatResponse>(endpoint, payload).pipe(
      tap({
        next: (response) => console.log('[TextAgent] Response:', response),
        error: (err) => console.error('[TextAgent] Error:', err),
      }),
    );
  }
}
