import { Component, input } from '@angular/core';
import { NgFor } from '@angular/common';
import { ChatMessage, ChatSender } from '../../models/chat.model';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [NgFor],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss'],
})
export class ChatComponent {
  public messages = input<ChatMessage[]>([]);

  public readonly ChatSender = ChatSender;
}
