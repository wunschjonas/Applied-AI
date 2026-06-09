import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

export interface ChatResponse {
  message: string;
}

@Injectable({
  providedIn: 'root',
})
export class ManagerAgentService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:8080';

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
