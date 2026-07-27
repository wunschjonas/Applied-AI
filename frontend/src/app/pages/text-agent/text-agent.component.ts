import { Component, OnInit, inject, signal } from '@angular/core';
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
export class TextAgentComponent implements OnInit {
  public chatFacade = inject(ChatFacade);
  public postFacade = inject(PostFacade);
  private readonly textAgentService = inject(TextAgentService);

  public generatedText = signal<string | null>(null);

  public ngOnInit(): void {
    const postId = this.postFacade.currentPostId();
    if (!postId) return;
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
        this.generatedText.set(response.message);
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
