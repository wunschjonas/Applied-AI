import { Component, inject } from '@angular/core';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { ChatPanelComponent } from '../../components/chat-panel/chat-panel.component';
import { ChatFacade } from '../../facades/chat.facade';
import { ChatSender } from '../../models/chat.model';

@Component({
  selector: 'app-image-agent',
  standalone: true,
  imports: [SidebarComponent, ChatPanelComponent],
  templateUrl: './image-agent.component.html',
  styleUrls: ['./image-agent.component.scss'],
})
export class ImageAgentComponent {
  public chatFacade = inject(ChatFacade);

  public onUserSend(text: string): void {
    this.chatFacade.updateImageAgentChat([
      ...this.chatFacade.imageAgentChat(),
      { sender: ChatSender.User, text },
    ]);
  }

  public onAgentSend(text: string): void {
    this.chatFacade.updateImageAgentChat([
      ...this.chatFacade.imageAgentChat(),
      { sender: ChatSender.Agent, text },
    ]);
  }
}
