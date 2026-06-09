import { Injectable, signal } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class PostFacade {
  private _currentPostId = signal<string | null>(null);
  public currentPostId = this._currentPostId.asReadonly();

  public updateCurrentPostId(id: string | null): void {
    this._currentPostId.update((_) => id);
  }
}
