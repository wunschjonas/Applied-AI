import { Component, input, output } from '@angular/core';
import { ChatComponent } from '../chat/chat.component';
import { ChatInputComponent } from '../chat-input/chat-input.component';
import { ChatMessage } from '../../models/chat.model';

@Component({
  selector: 'app-chat-panel',
  standalone: true,
  imports: [ChatComponent, ChatInputComponent],
  templateUrl: './chat-panel.component.html',
  styleUrls: ['./chat-panel.component.scss'],
})
export class ChatPanelComponent {
  public messages = input<ChatMessage[]>([]);
  public errorMessage = input<string>('');
  public userSend = output<string>();
}
