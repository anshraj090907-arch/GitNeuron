export type IndexStatusValue =
  | "pending" | "validating" | "cloning" | "chunking" | "embedding" | "ready" | "error";

export interface IndexStatus {
  repo_id: string;
  status: IndexStatusValue;
  message: string;
  files_indexed: number;
  chunks_indexed: number;
  repo_name: string;
  default_branch: string;
}

export interface SourceChunk {
  file_path: string;
  start_line: number;
  end_line: number;
  language: string;
  snippet: string;
  score: number;
}

export interface ReasoningStep {
  id: string;
  label: string;
  kind: "plan" | "retrieval" | "generation" | "tool" | "fallback" | "error";
  detail: string;
  status: "running" | "done" | "failed";
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: SourceChunk[];
  reasoning?: ReasoningStep[];
  modelUsed?: string;
  streaming?: boolean;
}

export interface FileTreeNode {
  name: string;
  type: "dir" | "file";
  path?: string;
  children?: FileTreeNode[];
}

export interface Template {
  id: string;
  name: string;
  description: string;
}

export interface ModelOption {
  id: string;
  provider: string;
  model: string;
  label: string;
  configured: boolean;
  is_default_chain: boolean;
}
