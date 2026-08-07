import { Component, input, output, signal } from '@angular/core';

@Component({
  selector: 'app-chat-input',
  standalone: true,
  imports: [],
  templateUrl: './chat-input.component.html',
  styleUrls: ['./chat-input.component.scss'],
})
export class ChatInputComponent {
  public disabled = input(false);
  public userSend = output<string>();

  public inputText = signal<string>('');

  public canSend(): boolean {
    return !this.disabled() && this.inputText().trim().length > 0;
  }

  public sendMessage(): void {
    if (this.disabled()) return;
    const text = this.inputText().trim();
    if (!text) return;
    this.userSend.emit(text);
    this.inputText.set('');
  }
}
