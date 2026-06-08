import { Component, inject } from '@angular/core';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { ChatPanelComponent } from '../../components/chat-panel/chat-panel.component';
import { ChatFacade } from '../../facades/chat.facade';
import { ChatSender } from '../../models/chat.model';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [SidebarComponent, ChatPanelComponent],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
})
export class HomeComponent {
  public chatFacade = inject(ChatFacade);

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
