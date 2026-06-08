import { Component, output, signal } from '@angular/core';

@Component({
  selector: 'app-chat-input',
  standalone: true,
  imports: [],
  templateUrl: './chat-input.component.html',
  styleUrls: ['./chat-input.component.scss'],
})
export class ChatInputComponent {
  public userSend = output<string>();
  public agentSend = output<string>();

  public inputText = signal<string>('');

  public sendMessage(): void {
    const text = this.inputText().trim();
    if (!text) return;
    this.userSend.emit(text);
    this.inputText.set('');
  }

  public simulateAgentMessage(): void {
    const text = this.inputText().trim();
    if (!text) return;
    this.agentSend.emit(text);
    this.inputText.set('');
  }
}
