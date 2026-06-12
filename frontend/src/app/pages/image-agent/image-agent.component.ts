import { Component, inject, signal } from '@angular/core';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { ChatPanelComponent } from '../../components/chat-panel/chat-panel.component';
import { ChatFacade } from '../../facades/chat.facade';
import { PostFacade } from '../../facades/post.facade';
import { ChatSender } from '../../models/chat.model';
import { ImageAgentService } from '../../services/image-agent.service';

@Component({
  selector: 'app-image-agent',
  standalone: true,
  imports: [SidebarComponent, ChatPanelComponent],
  templateUrl: './image-agent.component.html',
  styleUrls: ['./image-agent.component.scss'],
})
export class ImageAgentComponent {
  public chatFacade = inject(ChatFacade);
  public postFacade = inject(PostFacade);
  private readonly imageAgentService = inject(ImageAgentService);

  public generatedImageUrl = signal<string | null>(null);

  public onUserSend(text: string): void {
    const postId = this.postFacade.currentPostId();
    if (!postId) return;

    this.chatFacade.updateImageAgentChat([
      ...this.chatFacade.imageAgentChat(),
      { sender: ChatSender.User, text },
    ]);

    this.chatFacade.updateIsImageAgentWorking(true);

    this.imageAgentService.chat(text, postId).subscribe({
      next: (response) => {
        this.chatFacade.updateImageAgentChat([
          ...this.chatFacade.imageAgentChat(),
          { sender: ChatSender.Agent, text: response.message },
        ]);
        this.generatedImageUrl.set(response.message);
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
}
