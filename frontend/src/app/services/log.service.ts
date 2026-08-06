import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../core/api.config';
import { LogsResponse } from '../models/log.model';

export interface LogsDeleteResponse {
  deleted: number;
  scope: 'all' | 'post';
  post_id: string | null;
}

@Injectable({
  providedIn: 'root',
})
export class LogService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = API_BASE_URL;

  getManagerLogs() {
    return this.http.get<LogsResponse>(`${this.baseUrl}/api/agents/manager/logs`);
  }

  getTextLogs() {
    return this.http.get<LogsResponse>(`${this.baseUrl}/api/agents/text/logs`);
  }

  getImageLogs() {
    return this.http.get<LogsResponse>(`${this.baseUrl}/api/agents/image/logs`);
  }

  deleteAllLogs(): Observable<LogsDeleteResponse> {
    return this.http.delete<LogsDeleteResponse>(`${this.baseUrl}/api/logs`);
  }

  deleteLogsForPost(postId: string): Observable<LogsDeleteResponse> {
    return this.http.delete<LogsDeleteResponse>(`${this.baseUrl}/api/logs`, {
      params: { post_id: postId },
    });
  }
}
