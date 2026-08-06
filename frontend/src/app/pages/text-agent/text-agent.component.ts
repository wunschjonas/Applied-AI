import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs/operators';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { ChatPanelComponent } from '../../components/chat-panel/chat-panel.component';
import { PostContextComponent } from '../../components/post-context/post-context.component';
import { ArtifactFacade } from '../../facades/artifact.facade';
import { ChatFacade } from '../../facades/chat.facade';
import { PostFacade } from '../../facades/post.facade';
import { ChatSender } from '../../models/chat.model';
import { ArtifactSyncService } from '../../services/artifact-sync.service';
import { TextAgentService } from '../../services/text-agent.service';
import { httpErrorDetail } from '../../core/http-error';

@Component({
  selector: 'app-text-agent',
  standalone: true,
  imports: [SidebarComponent, ChatPanelComponent, PostContextComponent],
  templateUrl: './text-agent.component.html',
  styleUrls: ['./text-agent.component.scss'],
})
export class TextAgentComponent implements OnInit {
  public chatFacade = inject(ChatFacade);
  public postFacade = inject(PostFacade);
  public artifactFacade = inject(ArtifactFacade);
  private readonly textAgentService = inject(TextAgentService);
  private readonly artifactSync = inject(ArtifactSyncService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  public chatError = signal('');

  public ngOnInit(): void {
    this.reloadChat();
    this.router.events
      .pipe(
        filter((e): e is NavigationEnd => e instanceof NavigationEnd),
        filter(() => this.router.url.includes('/text_agent')),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => this.reloadChat());
  }

  private reloadChat(): void {
    const postId = this.postFacade.currentPostId();
    if (!postId) return;

    this.artifactSync.loadForPost(postId);
    this.textAgentService.getChatHistory(postId).subscribe({
      next: (history) => {
        const messages = history.messages.map((m) => ({
          sender: m.role === 'USER' ? ChatSender.User : ChatSender.Agent,
          text: m.content,
        }));
        this.chatFacade.updateTextAgentChat(messages);
      },
      error: (err) => console.error('[TextAgent] Failed to load history:', err),
    });
  }

  public onUserSend(text: string): void {
    const postId = this.postFacade.currentPostId();
    if (!postId) return;

    this.chatError.set('');
    this.chatFacade.updateTextAgentChat([
      ...this.chatFacade.textAgentChat(),
      { sender: ChatSender.User, text },
    ]);
    this.textAgentService.chat(text, postId).subscribe({
      next: (response) => {
        this.chatFacade.updateTextAgentChat([
          ...this.chatFacade.textAgentChat(),
          { sender: ChatSender.Agent, text: response.assistant_message },
        ]);
        this.artifactFacade.applyArtifacts(response.generated_artifacts);
      },
      error: (err) => {
        this.chatError.set(httpErrorDetail(err, 'Text-Agent-Anfrage fehlgeschlagen.'));
      },
    });
  }
}
