import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { ChatPanelComponent } from '../../components/chat-panel/chat-panel.component';
import { PostContextComponent } from '../../components/post-context/post-context.component';
import { ArtifactFacade } from '../../facades/artifact.facade';
import { ChatFacade } from '../../facades/chat.facade';
import { PostFacade } from '../../facades/post.facade';
import { ChatSender } from '../../models/chat.model';
import { ArtifactSyncService } from '../../services/artifact-sync.service';
import { ImageAgentService } from '../../services/image-agent.service';

@Component({
  selector: 'app-image-agent',
  standalone: true,
  imports: [SidebarComponent, ChatPanelComponent, PostContextComponent],
  templateUrl: './image-agent.component.html',
  styleUrls: ['./image-agent.component.scss'],
})
export class ImageAgentComponent implements OnInit, OnDestroy {
  public chatFacade = inject(ChatFacade);
  public postFacade = inject(PostFacade);
  public artifactFacade = inject(ArtifactFacade);

  private readonly imageAgentService = inject(ImageAgentService);
  private readonly artifactSync = inject(ArtifactSyncService);

  public sourceImage = signal<File | null>(null);
  public sourcePreviewUrl = signal<string | null>(null);

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

  public ngOnDestroy(): void {
    this.clearSourcePreview();
  }

  public onSourceImageSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    if (!file) {
      this.clearSourceImage();
      return;
    }
    if (!file.type.startsWith('image/')) {
      console.error('[ImageAgent] Only image files are allowed.');
      input.value = '';
      return;
    }
    this.clearSourcePreview();
    this.sourceImage.set(file);
    this.sourcePreviewUrl.set(URL.createObjectURL(file));
  }

  public clearSourceImage(): void {
    this.sourceImage.set(null);
    this.clearSourcePreview();
  }

  public onUserSend(text: string): void {
    const postId = this.postFacade.currentPostId();
    if (!postId) return;

    const reference = this.sourceImage();
    const displayText = reference
      ? `${text}\n[Referenzbild: ${reference.name}]`
      : text;

    this.chatFacade.updateImageAgentChat([
      ...this.chatFacade.imageAgentChat(),
      { sender: ChatSender.User, text: displayText },
    ]);

    this.chatFacade.updateIsImageAgentWorking(true);

    this.imageAgentService.chat(text, postId, reference).subscribe({
      next: (response) => {
        this.chatFacade.updateImageAgentChat([
          ...this.chatFacade.imageAgentChat(),
          { sender: ChatSender.Agent, text: response.assistant_message },
        ]);
        this.artifactFacade.applyArtifacts(response.generated_artifacts);
      },
      complete: () => this.chatFacade.updateIsImageAgentWorking(false),
      error: () => this.chatFacade.updateIsImageAgentWorking(false),
    });
  }

  public onAgentSend(text: string): void {
    this.chatFacade.updateImageAgentChat([
      ...this.chatFacade.imageAgentChat(),
      { sender: ChatSender.Agent, text },
    ]);
  }

  private clearSourcePreview(): void {
    const url = this.sourcePreviewUrl();
    if (url) {
      URL.revokeObjectURL(url);
    }
    this.sourcePreviewUrl.set(null);
  }
}
