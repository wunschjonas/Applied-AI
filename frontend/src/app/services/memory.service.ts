import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface MemoryStoreResponse {
  status: string;
}

export interface MemorySearchResponse {
  query: string;
  results: string[];
}

export interface MemoryListResponse {
  entries: string[];
}

export interface MemoryUploadResponse {
  stored_chunks: number;
  filename: string;
  kind: string;
  preview: string;
}

@Injectable({
  providedIn: 'root',
})
export class MemoryService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:8080';

  store(content: string, tags: string[]): Observable<MemoryStoreResponse> {
    return this.http.post<MemoryStoreResponse>(`${this.baseUrl}/api/memory/store`, {
      content,
      tags,
    });
  }

  search(q: string): Observable<MemorySearchResponse> {
    return this.http.get<MemorySearchResponse>(`${this.baseUrl}/api/memory/search`, {
      params: { q },
    });
  }

  list(): Observable<MemoryListResponse> {
    return this.http.get<MemoryListResponse>(`${this.baseUrl}/api/memory/list`);
  }

  upload(file: File): Observable<MemoryUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<MemoryUploadResponse>(`${this.baseUrl}/api/memory/upload`, formData);
  }
}
