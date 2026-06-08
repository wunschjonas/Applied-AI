export enum ChatSender {
  User = 'USER',
  Agent = 'AGENT',
}

export interface ChatMessage {
  sender: ChatSender;
  text: string;
}
