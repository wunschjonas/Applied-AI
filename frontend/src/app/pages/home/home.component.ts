import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { ChatPanelComponent } from '../../components/chat-panel/chat-panel.component';
import { PostContextComponent } from '../../components/post-context/post-context.component';
import { ArtifactFacade } from '../../facades/artifact.facade';
import { ChatFacade } from '../../facades/chat.facade';
import { PostFacade } from '../../facades/post.facade';
import { ArtifactSyncService } from '../../services/artifact-sync.service';
import { PostService } from '../../services/post.service';
import { ManagerAgentService } from '../../services/manager-agent.service';
import { ChatSender } from '../../models/chat.model';
import { Post } from '../../models/post.model';

const FIELD_LABELS: Record<string, string> = {
  topic: 'Thema',
  platform: 'Plattform',
  target_audience: 'Zielgruppe',
  tone_of_voice: 'Tonalität',
  text_context: 'Textkontext',
  text_length: 'Textlänge',
  image_context: 'Bildmotiv',
  image_style: 'Bildstil',
};

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [
    SidebarComponent,
    ChatPanelComponent,
    PostContextComponent,
    FormsModule,
    RouterLink,
  ],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
})
export class HomeComponent implements OnInit {
  public chatFacade = inject(ChatFacade);
  public postFacade = inject(PostFacade);
  public artifactFacade = inject(ArtifactFacade);
  private readonly postService = inject(PostService);
  private readonly managerAgentService = inject(ManagerAgentService);
  private readonly artifactSync = inject(ArtifactSyncService);

  public postTitle = signal('');
  public isCreating = signal(false);
  public allPosts = signal<Post[]>([]);
  public isLoadingPosts = signal(false);

  public ngOnInit(): void {
    this.loadPosts();
    const postId = this.postFacade.currentPostId();
    if (postId) {
      this.loadManagerChatHistory(postId);
      this.artifactSync.loadForPost(postId);
    }
  }

  public loadPosts(): void {
    this.isLoadingPosts.set(true);
    this.postService.getAllPosts().subscribe({
      next: (posts) => this.allPosts.set(posts),
      error: (err) => console.error('[Home] Failed to load posts:', err),
      complete: () => this.isLoadingPosts.set(false),
    });
  }

  public selectPost(post: Post): void {
    this.postFacade.updateCurrentPost({
      post_id: post.id,
      title: post.title,
      created_at: '',
    });
    this.loadManagerChatHistory(post.id);
    this.artifactFacade.applyPreview(post.preview);
    this.artifactFacade.updateMissingFields(
      post.missing_fields ?? this.missingFieldsFromPost(post),
    );
  }

  public createPost(): void {
    const title = this.postTitle().trim();
    if (!title) return;
    this.isCreating.set(true);
    console.log('[Home] POST /api/posts/init', { title });
    this.postService.initPost(title).subscribe({
      next: (response) => {
        console.log('[Home] Response:', response);
        this.postFacade.updateCurrentPost(response);
        const welcome = response.welcome_message?.trim();
        this.chatFacade.updateMainAgentChat(
          welcome ? [{ sender: ChatSender.Agent, text: welcome }] : [],
        );
        this.artifactFacade.reset();
        this.artifactFacade.updateMissingFields(
          response.missing_fields ?? ['topic', 'platform', 'target_audience', 'tone_of_voice'],
        );
        this.postTitle.set('');
        this.loadPosts();
      },
      error: (err) => {
        console.error('[Home] Error:', err);
        this.isCreating.set(false);
      },
      complete: () => this.isCreating.set(false),
    });
  }

  public onUserSend(text: string): void {
    const postId = this.postFacade.currentPostId();
    if (!postId) return;

    this.chatFacade.updateMainAgentChat([
      ...this.chatFacade.mainAgentChat(),
      { sender: ChatSender.User, text },
    ]);
    this.chatFacade.updateIsMainAgentWorking(true);
    this.managerAgentService.chat(text, postId).subscribe({
      next: (response) => {
        this.chatFacade.updateMainAgentChat([
          ...this.chatFacade.mainAgentChat(),
          { sender: ChatSender.Agent, text: response.assistant_message },
        ]);
        this.artifactFacade.applyArtifacts(response.generated_artifacts);
        this.artifactFacade.updateMissingFields(response.missing_fields);
        if (response.post_updates && Object.keys(response.post_updates).length) {
          this.loadPosts();
        }
      },
      complete: () => this.chatFacade.updateIsMainAgentWorking(false),
      error: () => this.chatFacade.updateIsMainAgentWorking(false),
    });
  }

  public fieldLabel(field: string): string {
    return FIELD_LABELS[field] ?? field;
  }

  private missingFieldsFromPost(post: Post): string[] {
    const fields: (keyof Post)[] = [
      'topic',
      'platform',
      'target_audience',
      'tone_of_voice',
      'text_context',
      'text_length',
      'image_context',
      'image_style',
    ];
    return fields.filter((field) => !post[field]);
  }

  private loadManagerChatHistory(postId: string): void {
    this.managerAgentService.getChatHistory(postId).subscribe({
      next: (history) => {
        const messages = history.messages.map((m) => ({
          sender: m.role === 'USER' ? ChatSender.User : ChatSender.Agent,
          text: m.content,
        }));
        this.chatFacade.updateMainAgentChat(messages);
      },
      error: (err) =>
        console.error('[Home] Failed to load manager chat history:', err),
    });
  }
}
