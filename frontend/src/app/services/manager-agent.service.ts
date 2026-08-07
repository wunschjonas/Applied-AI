import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
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
  /** Steckbrief fields that are still open, in the order the manager will ask for them. */
  missing_fields?: string[];
  /** True when specialists should be started via /generate next. */
  generation_pending?: boolean;
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
    return this.http.post<ChatResponse>(`${this.baseUrl}/api/agents/manager/chat`, {
      message,
      post_id: postId,
    });
  }

  public generate(postId: string): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.baseUrl}/api/agents/manager/generate`, {
      post_id: postId,
    });
  }
}
