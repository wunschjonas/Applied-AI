export interface LogEntry {
  id: string;
  run_id: string;
  agent: string;
  timestamp: string;
  step: string;
  tool_called: string | null;
  thought: string | null;
  action: string;
  observation: string | null;
  input_summary: string;
  output_summary: string | null;
  status: 'success' | 'error' | 'skipped';
  duration_ms: number;
}

export interface LogsResponse {
  agent: string;
  total: number;
  logs: LogEntry[];
}
