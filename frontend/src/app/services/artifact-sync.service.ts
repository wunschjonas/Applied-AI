import { Injectable, inject } from '@angular/core';
import { ArtifactFacade } from '../facades/artifact.facade';
import { PostService } from './post.service';

/**
 * Loads the stored artifacts of a post into the ArtifactFacade. Uses GET /api/posts/:id
 * instead of the preview endpoint, which answers 404 while a post has no preview yet.
 */
@Injectable({
  providedIn: 'root',
})
export class ArtifactSyncService {
  private readonly postService = inject(PostService);
  private readonly artifactFacade = inject(ArtifactFacade);

  public loadForPost(postId: string): void {
    this.postService.getPost(postId).subscribe({
      next: (post) => this.artifactFacade.applyPreview(post.preview),
      error: (err) => {
        console.error('[ArtifactSync] Failed to load post artifacts:', err);
        this.artifactFacade.reset();
      },
    });
  }
}
