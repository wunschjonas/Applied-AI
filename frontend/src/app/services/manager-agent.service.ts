import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { API_BASE_URL } from '../core/api.config';
import { AgentChatHistory } from '../models/chat.model';
import { GeneratedArtifacts } from '../models/artifact.model';

export interface ChatResponse {
  chat_id: string;
  assistant_message: string;
  used_agents?: string[];
  generated_artifacts?: GeneratedArtifacts;
  trace_id?: string;
  /** Post fields the manager filled from this message. */
  post_updates?: Record<string, unknown>;
  /** Brief fields that are still open, in the order the manager will ask for them. */
  missing_fields?: string[];
}

@Injectable({
  providedIn: 'root',
})
export class ManagerAgentService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = API_BASE_URL;

  public getChatHistory(postId: string): Observable<AgentChatHistory> {
    return this.http.get<AgentChatHistory>(
      `${this.baseUrl}/api/agents/manager/chats/${postId}::manager_agent`,
    );
  }

  public chat(message: string, postId: string): Observable<ChatResponse> {
    const endpoint = `${this.baseUrl}/api/agents/manager/chat`;
    const payload = { message, post_id: postId };
    console.log('[ManagerAgent] POST', endpoint, payload);
    return this.http.post<ChatResponse>(endpoint, payload).pipe(
      tap({
        next: (response) => console.log('[ManagerAgent] Response:', response),
        error: (err) => console.error('[ManagerAgent] Error:', err),
      }),
    );
  }
}
