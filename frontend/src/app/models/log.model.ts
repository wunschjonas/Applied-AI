// HINWEIS: Dies ist ein Vorschlag für die Modellstruktur des Log-Features.
// Die finale Struktur richtet sich nach der Backend-Implementierung.

export enum LogLevel {
  Debug = 'DEBUG',
  Info = 'INFO',
  Warning = 'WARNING',
  Error = 'ERROR',
}

export enum LogSource {
  System = 'SYSTEM',
  ManagerAgent = 'MANAGER_AGENT',
  TextAgent = 'TEXT_AGENT',
  ImageAgent = 'IMAGE_AGENT',
  RagAgent = 'RAG_AGENT',
  Api = 'API',
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  source: LogSource;
  message: string;
  details?: string;
  post_id?: string;
}

export interface LogsResponse {
  logs: LogEntry[];
  total: number;
}

export interface LogsQueryParams {
  level?: LogLevel;
  source?: LogSource;
  post_id?: string;
  limit?: number;
  offset?: number;
}
