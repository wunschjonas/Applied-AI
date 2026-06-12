import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { ChatPanelComponent } from '../../components/chat-panel/chat-panel.component';
import { ChatFacade } from '../../facades/chat.facade';
import { PostFacade } from '../../facades/post.facade';
import { PostService } from '../../services/post.service';
import { ManagerAgentService } from '../../services/manager-agent.service';
import { ChatSender } from '../../models/chat.model';
import { Post } from '../../models/post.model';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [SidebarComponent, ChatPanelComponent, FormsModule, DatePipe],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
})
export class HomeComponent implements OnInit {
  public chatFacade = inject(ChatFacade);
  public postFacade = inject(PostFacade);
  private readonly postService = inject(PostService);
  private readonly managerAgentService = inject(ManagerAgentService);

  public postTitle = signal('');
  public isCreating = signal(false);
  public allPosts = signal<Post[]>([]);
  public isLoadingPosts = signal(false);

  public ngOnInit(): void {
    this.loadPosts();
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
          { sender: ChatSender.Agent, text: response.message },
        ]);
      },
      complete: () => this.chatFacade.updateIsMainAgentWorking(false),
      error: () => this.chatFacade.updateIsMainAgentWorking(false),
    });
  }

  public onAgentSend(text: string): void {
    this.chatFacade.updateMainAgentChat([
      ...this.chatFacade.mainAgentChat(),
      { sender: ChatSender.Agent, text },
    ]);
  }
}
