import { Component, OnInit, inject } from '@angular/core';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { PostContextComponent } from '../../components/post-context/post-context.component';
import { ArtifactFacade } from '../../facades/artifact.facade';
import { PostFacade } from '../../facades/post.facade';
import { ArtifactSyncService } from '../../services/artifact-sync.service';

@Component({
  selector: 'app-preview',
  standalone: true,
  imports: [SidebarComponent, PostContextComponent],
  templateUrl: './preview.component.html',
  styleUrls: ['./preview.component.scss'],
})
export class PreviewComponent implements OnInit {
  public postFacade = inject(PostFacade);
  public artifactFacade = inject(ArtifactFacade);
  private readonly artifactSync = inject(ArtifactSyncService);

  public ngOnInit(): void {
    const postId = this.postFacade.currentPostId();
    if (postId) {
      this.artifactSync.loadForPost(postId);
    }
  }
}
