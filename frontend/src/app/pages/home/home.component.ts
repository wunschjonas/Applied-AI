import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
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
import { httpErrorDetail } from '../../core/http-error';

const GENERAL_FIELD_KEYS = [
  'topic',
  'platform',
  'target_audience',
  'tone_of_voice',
] as const;

const TEXT_FIELD_KEYS = ['text_context', 'text_length'] as const;

const IMAGE_FIELD_KEYS = ['image_context', 'image_style'] as const;

const FIELD_KEYS = [
  ...GENERAL_FIELD_KEYS,
  ...TEXT_FIELD_KEYS,
  ...IMAGE_FIELD_KEYS,
] as const;

const FIELD_LABELS: Record<(typeof FIELD_KEYS)[number], string> = {
  topic: 'Thema',
  platform: 'Plattform',
  target_audience: 'Zielgruppe',
  tone_of_voice: 'Tonalität',
  text_context: 'Textkontext',
  text_length: 'Textlänge',
  image_context: 'Bildkontext',
  image_style: 'Bildstil',
};

const PLATFORM_DISPLAY: Record<string, string> = {
  linkedin: 'LinkedIn',
  instagram: 'Instagram',
  x: 'X',
  blog: 'Blog',
  tiktok: 'TikTok',
  facebook: 'Facebook',
};

function formatFieldValue(key: string, value: string): string {
  if (key === 'platform') {
    return PLATFORM_DISPLAY[value.toLowerCase()] ?? value;
  }
  return value;
}

export interface PostFieldRow {
  key: (typeof FIELD_KEYS)[number];
  label: string;
  filled: boolean;
  value: string;
}

export interface PostFieldGroup {
  id: 'general' | 'text' | 'image';
  title: string;
  rows: PostFieldRow[];
}

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [
    SidebarComponent,
    ChatPanelComponent,
    PostContextComponent,
    FormsModule,
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
  public isDeleting = signal(false);
  public allPosts = signal<Post[]>([]);
  public isLoadingPosts = signal(false);
  public chatError = signal('');
  public selectedPost = signal<Post | null>(null);

  public fieldGroups = computed<PostFieldGroup[]>(() => {
    const post = this.selectedPost();
    const toRows = (keys: readonly (typeof FIELD_KEYS)[number][]): PostFieldRow[] =>
      keys.map((key) => {
        const raw = post?.[key];
        const trimmed = typeof raw === 'string' ? raw.trim() : '';
        return {
          key,
          label: FIELD_LABELS[key],
          filled: trimmed.length > 0,
          value: formatFieldValue(key, trimmed),
        };
      });

    return [
      { id: 'general', title: 'Allgemein', rows: toRows(GENERAL_FIELD_KEYS) },
      { id: 'text', title: 'Text', rows: toRows(TEXT_FIELD_KEYS) },
      { id: 'image', title: 'Bild', rows: toRows(IMAGE_FIELD_KEYS) },
    ];
  });

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
      next: (posts) => {
        this.allPosts.set(posts);
        const currentId = this.postFacade.currentPostId();
        if (currentId) {
          const match = posts.find((post) => post.id === currentId) ?? null;
          this.selectedPost.set(match);
        }
      },
      error: (err) => {
        this.chatError.set(httpErrorDetail(err, 'Posts konnten nicht geladen werden.'));
      },
      complete: () => this.isLoadingPosts.set(false),
    });
  }

  public selectPost(post: Post): void {
    this.selectedPost.set(post);
    this.postFacade.updateCurrentPost({
      post_id: post.id,
      title: post.title,
      created_at: '',
    });
    this.loadManagerChatHistory(post.id);
    this.artifactFacade.applyPreview(post.preview);
  }

  public deleteSelectedPost(): void {
    const post = this.postFacade.currentPost();
    const postId = post?.post_id;
    if (!postId || this.isDeleting()) return;

    const title = post?.title?.trim() || postId;
    if (!confirm(`Post „${title}“ wirklich löschen?`)) return;

    this.isDeleting.set(true);
    this.chatError.set('');
    this.postService.deletePost(postId).subscribe({
      next: () => {
        this.postFacade.updateCurrentPost(null);
        this.selectedPost.set(null);
        this.chatFacade.updateMainAgentChat([]);
        this.chatFacade.updateTextAgentChat([]);
        this.chatFacade.updateImageAgentChat([]);
        this.artifactFacade.reset();
        this.loadPosts();
      },
      error: (err) => {
        this.chatError.set(httpErrorDetail(err, 'Post konnte nicht gelöscht werden.'));
        this.isDeleting.set(false);
      },
      complete: () => this.isDeleting.set(false),
    });
  }

  public createPost(): void {
    const title = this.postTitle().trim();
    if (!title) return;
    this.isCreating.set(true);
    this.chatError.set('');
    this.postService.initPost(title).subscribe({
      next: (response) => {
        this.postFacade.updateCurrentPost(response);
        this.selectedPost.set({
          id: response.post_id,
          title: response.title,
          status: 'draft',
          missing_fields:
            response.missing_fields ??
            ['topic', 'platform', 'target_audience', 'tone_of_voice'],
        });
        const welcome = response.welcome_message?.trim();
        this.chatFacade.updateMainAgentChat(
          welcome ? [{ sender: ChatSender.Agent, text: welcome }] : [],
        );
        this.artifactFacade.reset();
        this.postTitle.set('');
        this.loadPosts();
      },
      error: (err) => {
        this.chatError.set(httpErrorDetail(err, 'Post konnte nicht erstellt werden.'));
        this.isCreating.set(false);
      },
      complete: () => this.isCreating.set(false),
    });
  }

  public onUserSend(text: string): void {
    const postId = this.postFacade.currentPostId();
    if (!postId) return;

    this.chatError.set('');
    this.chatFacade.updateMainAgentChat([
      ...this.chatFacade.mainAgentChat(),
      { sender: ChatSender.User, text },
    ]);
    this.managerAgentService.chat(text, postId).subscribe({
      next: (response) => {
        this.chatFacade.updateMainAgentChat([
          ...this.chatFacade.mainAgentChat(),
          { sender: ChatSender.Agent, text: response.assistant_message },
        ]);
        this.artifactFacade.applyArtifacts(response.generated_artifacts);
        this.loadPosts();
      },
      error: (err) => {
        this.chatError.set(httpErrorDetail(err, 'Manager-Anfrage fehlgeschlagen.'));
      },
    });
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
      error: (err) => {
        this.chatError.set(httpErrorDetail(err, 'Chat-Verlauf konnte nicht geladen werden.'));
      },
    });
  }
}
