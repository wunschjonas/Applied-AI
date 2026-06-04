import { Component, inject } from '@angular/core';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { ChatPanelComponent } from '../../components/chat-panel/chat-panel.component';
import { ChatFacade } from '../../facades/chat.facade';
import { ChatSender } from '../../models/chat.model';

@Component({
  selector: 'app-text-agent',
  standalone: true,
  imports: [SidebarComponent, ChatPanelComponent],
  templateUrl: './text-agent.component.html',
  styleUrls: ['./text-agent.component.scss'],
})
export class TextAgentComponent {
  public chatFacade = inject(ChatFacade);

  public onUserSend(text: string): void {
    this.chatFacade.updateTextAgentChat([
      ...this.chatFacade.textAgentChat(),
      { sender: ChatSender.User, text },
    ]);
  }

  public onAgentSend(text: string): void {
    this.chatFacade.updateTextAgentChat([
      ...this.chatFacade.textAgentChat(),
      { sender: ChatSender.Agent, text },
    ]);
  }
}
