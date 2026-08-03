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

export interface MemoryListEntry {
  content: string;
  content_hash: string;
  tags: string[];
}

export interface MemoryListResponse {
  entries: MemoryListEntry[];
}

export interface MemoryUploadResponse {
  stored_chunks: number;
  filename: string;
  kind: string;
  preview: string;
}

export interface MemoryDeleteResponse {
  status: string;
  content_hash: string;
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
    // Explicit filename helps some browsers/proxies keep the .pdf suffix for type detection.
    formData.append('file', file, file.name || 'upload.bin');
    return this.http.post<MemoryUploadResponse>(`${this.baseUrl}/api/memory/upload`, formData);
  }

  delete(contentHash: string): Observable<MemoryDeleteResponse> {
    return this.http.delete<MemoryDeleteResponse>(
      `${this.baseUrl}/api/memory/${encodeURIComponent(contentHash)}`
    );
  }
}
