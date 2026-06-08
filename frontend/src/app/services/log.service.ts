import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({
  providedIn: 'root',
})
export class LogService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:8080';

  getManagerLogs() {
    return this.http.get(`${this.baseUrl}/api/agents/manager/logs`);
  }

  getTextLogs() {
    return this.http.get(`${this.baseUrl}/api/agents/text/logs`);
  }

  getImageLogs() {
    return this.http.get(`${this.baseUrl}/api/agents/image/logs`);
  }
}
