import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { API_BASE_URL } from '../core/api.config';
import { InitPostResponse, Post } from '../models/post.model';

@Injectable({
  providedIn: 'root',
})
export class PostService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = API_BASE_URL;

  /** POST /api/posts/init */
  initPost(title: string): Observable<InitPostResponse> {
    return this.http.post<InitPostResponse>(`${this.baseUrl}/api/posts/init`, {
      title,
    });
  }

  /** GET /api/posts */
  getAllPosts(): Observable<Post[]> {
    return this.http.get<Post[]>(`${this.baseUrl}/api/posts`);
  }

  /** GET /api/posts/:postId */
  getPost(postId: string): Observable<Post> {
    return this.http.get<Post>(`${this.baseUrl}/api/posts/${postId}`);
  }

  /** DELETE /api/posts/:postId */
  deletePost(postId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/api/posts/${postId}`);
  }
}
