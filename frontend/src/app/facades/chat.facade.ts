import { Injectable, signal } from '@angular/core';
import { ChatMessage } from '../models/chat.model';

@Injectable({
  providedIn: 'root',
})
export class ChatFacade {
  private _mainAgentChat = signal<ChatMessage[]>([]);
  public mainAgentChat = this._mainAgentChat.asReadonly();

  public updateMainAgentChat(value: ChatMessage[]): void {
    this._mainAgentChat.update((_) => value);
  }

  private _imageAgentChat = signal<ChatMessage[]>([]);
  public imageAgentChat = this._imageAgentChat.asReadonly();

  public updateImageAgentChat(value: ChatMessage[]): void {
    this._imageAgentChat.update((_) => value);
  }

  private _textAgentChat = signal<ChatMessage[]>([]);
  public textAgentChat = this._textAgentChat.asReadonly();

  public updateTextAgentChat(value: ChatMessage[]): void {
    this._textAgentChat.update((_) => value);
  }
}
