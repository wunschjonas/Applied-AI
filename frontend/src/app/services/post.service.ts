import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  AgentTraceStep,
  CreatePostRequest,
  HealthResponse,
  Post,
  PostPreview,
  UpdatePostRequest,
} from '../models/post.model';

@Injectable({
  providedIn: 'root',
})
export class PostService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:8080';

  /** GET /health */
  getHealth(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${this.baseUrl}/health`);
  }

  /** POST /api/posts */
  createPost(body: CreatePostRequest): Observable<Post> {
    return this.http.post<Post>(`${this.baseUrl}/api/posts`, body);
  }

  /** GET /api/posts */
  getAllPosts(): Observable<Post[]> {
    return this.http.get<Post[]>(`${this.baseUrl}/api/posts`);
  }

  /** GET /api/posts/:postId */
  getPost(postId: string): Observable<Post> {
    return this.http.get<Post>(`${this.baseUrl}/api/posts/${postId}`);
  }

  /** PUT /api/posts/:postId */
  updatePost(postId: string, body: UpdatePostRequest): Observable<Post> {
    return this.http.put<Post>(`${this.baseUrl}/api/posts/${postId}`, body);
  }

  /** POST /api/posts/:postId/generate-preview */
  generatePreview(postId: string): Observable<PostPreview> {
    return this.http.post<PostPreview>(
      `${this.baseUrl}/api/posts/${postId}/generate-preview`,
      {}
    );
  }

  /** GET /api/posts/:postId/preview */
  getPreview(postId: string): Observable<PostPreview> {
    return this.http.get<PostPreview>(
      `${this.baseUrl}/api/posts/${postId}/preview`
    );
  }

  /** GET /api/posts/:postId/agent-trace */
  getAgentTrace(postId: string): Observable<AgentTraceStep[]> {
    return this.http.get<AgentTraceStep[]>(
      `${this.baseUrl}/api/posts/${postId}/agent-trace`
    );
  }

  /** DELETE /api/posts/:postId */
  deletePost(postId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/api/posts/${postId}`);
  }
}
