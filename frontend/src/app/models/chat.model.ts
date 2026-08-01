export enum ChatSender {
  User = 'USER',
  Agent = 'AGENT',
}

export interface ChatMessage {
  sender: ChatSender;
  text: string;
}

export interface AgentChatHistoryMessage {
  role: string;
  content: string;
}

export interface AgentChatHistory {
  id: string;
  agent: string;
  created_at: string;
  updated_at: string;
  messages: AgentChatHistoryMessage[];
}
