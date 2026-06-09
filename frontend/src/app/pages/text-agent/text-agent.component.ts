import { Component, inject } from '@angular/core';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { ChatPanelComponent } from '../../components/chat-panel/chat-panel.component';
import { ChatFacade } from '../../facades/chat.facade';
import { PostFacade } from '../../facades/post.facade';
import { ChatSender } from '../../models/chat.model';
import { TextAgentService } from '../../services/text-agent.service';

@Component({
  selector: 'app-text-agent',
  standalone: true,
  imports: [SidebarComponent, ChatPanelComponent],
  templateUrl: './text-agent.component.html',
  styleUrls: ['./text-agent.component.scss'],
})
export class TextAgentComponent {
  public chatFacade = inject(ChatFacade);
  public postFacade = inject(PostFacade);
  private readonly textAgentService = inject(TextAgentService);

  public onUserSend(text: string): void {
    const postId = this.postFacade.currentPostId();
    if (!postId) return;

    this.chatFacade.updateTextAgentChat([
      ...this.chatFacade.textAgentChat(),
      { sender: ChatSender.User, text },
    ]);
    this.chatFacade.updateIsTextAgentWorking(true);
    this.textAgentService.chat(text, postId).subscribe({
      next: (response) => {
        this.chatFacade.updateTextAgentChat([
          ...this.chatFacade.textAgentChat(),
          { sender: ChatSender.Agent, text: response.message },
        ]);
      },
      complete: () => this.chatFacade.updateIsTextAgentWorking(false),
      error: () => this.chatFacade.updateIsTextAgentWorking(false),
    });
  }

  public onAgentSend(text: string): void {
    this.chatFacade.updateTextAgentChat([
      ...this.chatFacade.textAgentChat(),
      { sender: ChatSender.Agent, text },
    ]);
  }
}
