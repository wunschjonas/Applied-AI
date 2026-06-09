export interface LogEntry {
  id: string;
  agent: string;
  timestamp: string;
  action: string;
  input_summary: string;
  status: string;
  duration_ms: number;
}

export interface LogsResponse {
  agent: string;
  total: number;
  logs: LogEntry[];
}
