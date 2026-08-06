import { Component, OnInit, inject, signal } from '@angular/core';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { ChatPanelComponent } from '../../components/chat-panel/chat-panel.component';
import { PostContextComponent } from '../../components/post-context/post-context.component';
import { ArtifactFacade } from '../../facades/artifact.facade';
import { ChatFacade } from '../../facades/chat.facade';
import { PostFacade } from '../../facades/post.facade';
import { ChatSender } from '../../models/chat.model';
import { ArtifactSyncService } from '../../services/artifact-sync.service';
import { ImageAgentService } from '../../services/image-agent.service';
import { httpErrorDetail } from '../../core/http-error';

@Component({
  selector: 'app-image-agent',
  standalone: true,
  imports: [SidebarComponent, ChatPanelComponent, PostContextComponent],
  templateUrl: './image-agent.component.html',
  styleUrls: ['./image-agent.component.scss'],
})
export class ImageAgentComponent implements OnInit {
  public chatFacade = inject(ChatFacade);
  public postFacade = inject(PostFacade);
  public artifactFacade = inject(ArtifactFacade);

  private readonly imageAgentService = inject(ImageAgentService);
  private readonly artifactSync = inject(ArtifactSyncService);

  public chatError = signal('');

  public ngOnInit(): void {
    const postId = this.postFacade.currentPostId();
    if (!postId) return;

    this.artifactSync.loadForPost(postId);
    this.imageAgentService.getChatHistory(postId).subscribe({
      next: (history) => {
        const messages = history.messages.map((m) => ({
          sender: m.role === 'USER' ? ChatSender.User : ChatSender.Agent,
          text: m.content,
        }));
        this.chatFacade.updateImageAgentChat(messages);
      },
      error: (err) =>
        console.error('[ImageAgent] Failed to load history:', err),
    });
  }

  public onUserSend(text: string): void {
    const postId = this.postFacade.currentPostId();
    if (!postId) return;

    this.chatError.set('');
    this.chatFacade.updateImageAgentChat([
      ...this.chatFacade.imageAgentChat(),
      { sender: ChatSender.User, text },
    ]);

    this.chatFacade.updateIsImageAgentWorking(true);

    this.imageAgentService.chat(text, postId).subscribe({
      next: (response) => {
        this.chatFacade.updateImageAgentChat([
          ...this.chatFacade.imageAgentChat(),
          { sender: ChatSender.Agent, text: response.assistant_message },
        ]);
        this.artifactFacade.applyArtifacts(response.generated_artifacts);
      },
      complete: () => this.chatFacade.updateIsImageAgentWorking(false),
      error: (err) => {
        this.chatFacade.updateIsImageAgentWorking(false);
        this.chatError.set(httpErrorDetail(err, 'Image-Agent-Anfrage fehlgeschlagen.'));
      },
    });
  }
}
