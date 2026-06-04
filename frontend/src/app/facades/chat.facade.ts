import { Injectable, signal } from '@angular/core';
import { ChatMessage } from '../models/chat.model';

@Injectable({
  providedIn: 'root',
})
export class ChatFacade {
  // --- Main Agent ---

  private _mainAgentChat = signal<ChatMessage[]>([]);
  public mainAgentChat = this._mainAgentChat.asReadonly();

  public updateMainAgentChat(value: ChatMessage[]): void {
    this._mainAgentChat.update((_) => value);
  }

  private _isMainAgentWorking = signal<boolean>(false);
  public isMainAgentWorking = this._isMainAgentWorking.asReadonly();

  public updateIsMainAgentWorking(value: boolean): void {
    this._isMainAgentWorking.update((_) => value);
  }

  // --- Image Agent ---

  private _imageAgentChat = signal<ChatMessage[]>([]);
  public imageAgentChat = this._imageAgentChat.asReadonly();

  public updateImageAgentChat(value: ChatMessage[]): void {
    this._imageAgentChat.update((_) => value);
  }

  private _isImageAgentWorking = signal<boolean>(false);
  public isImageAgentWorking = this._isImageAgentWorking.asReadonly();

  public updateIsImageAgentWorking(value: boolean): void {
    this._isImageAgentWorking.update((_) => value);
  }

  // --- Text Agent ---

  private _textAgentChat = signal<ChatMessage[]>([]);
  public textAgentChat = this._textAgentChat.asReadonly();

  public updateTextAgentChat(value: ChatMessage[]): void {
    this._textAgentChat.update((_) => value);
  }

  private _isTextAgentWorking = signal<boolean>(false);
  public isTextAgentWorking = this._isTextAgentWorking.asReadonly();

  public updateIsTextAgentWorking(value: boolean): void {
    this._isTextAgentWorking.update((_) => value);
  }
}
