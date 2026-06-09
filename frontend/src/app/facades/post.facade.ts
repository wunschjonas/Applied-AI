import { Injectable, computed, signal } from '@angular/core';
import { InitPostResponse } from '../models/post.model';

@Injectable({
  providedIn: 'root',
})
export class PostFacade {
  private _currentPost = signal<InitPostResponse | null>(null);
  public currentPost = this._currentPost.asReadonly();
  public currentPostId = computed(() => this._currentPost()?.post_id ?? null);

  public updateCurrentPost(post: InitPostResponse | null): void {
    this._currentPost.update((_) => post);
  }
}
