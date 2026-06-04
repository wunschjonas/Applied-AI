import { Component, inject, signal } from '@angular/core';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { ChatComponent } from '../../components/chat/chat.component';
import { ChatFacade } from '../../facades/chat.facade';
import { ChatSender } from '../../models/chat.model';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [SidebarComponent, ChatComponent],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
})
export class HomeComponent {
  public chatFacade = inject(ChatFacade);

  public inputText = signal<string>('');

  public sendMessage(): void {
    const text = this.inputText().trim();
    if (!text) return;

    const updatedChat = [
      ...this.chatFacade.mainAgentChat(),
      { sender: ChatSender.User, text },
    ];
    this.chatFacade.updateMainAgentChat(updatedChat);
    this.inputText.set('');
  }

  public simulateAgentMessage(): void {
    const text = this.inputText().trim();
    if (!text) return;

    const updatedChat = [
      ...this.chatFacade.mainAgentChat(),
      { sender: ChatSender.Agent, text },
    ];
    this.chatFacade.updateMainAgentChat(updatedChat);
    this.inputText.set('');
  }
}
