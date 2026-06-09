import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { ChatPanelComponent } from '../../components/chat-panel/chat-panel.component';
import { ChatFacade } from '../../facades/chat.facade';
import { PostFacade } from '../../facades/post.facade';
import { PostService } from '../../services/post.service';
import { ChatSender } from '../../models/chat.model';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [SidebarComponent, ChatPanelComponent, FormsModule],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
})
export class HomeComponent {
  public chatFacade = inject(ChatFacade);
  public postFacade = inject(PostFacade);
  private readonly postService = inject(PostService);

  public postTitle = signal('');
  public isCreating = signal(false);

  public createPost(): void {
    const title = this.postTitle().trim();
    if (!title) return;
    this.isCreating.set(true);
    console.log('[Home] POST /api/posts/init', { title });
    this.postService.initPost(title).subscribe({
      next: (response) => {
        console.log('[Home] Response:', response);
        this.postFacade.updateCurrentPostId(response.post_id);
        this.postTitle.set('');
      },
      error: (err) => {
        console.error('[Home] Error:', err);
        this.isCreating.set(false);
      },
      complete: () => this.isCreating.set(false),
    });
  }

  public onUserSend(text: string): void {
    this.chatFacade.updateMainAgentChat([
      ...this.chatFacade.mainAgentChat(),
      { sender: ChatSender.User, text },
    ]);
  }

  public onAgentSend(text: string): void {
    this.chatFacade.updateMainAgentChat([
      ...this.chatFacade.mainAgentChat(),
      { sender: ChatSender.Agent, text },
    ]);
  }
}
