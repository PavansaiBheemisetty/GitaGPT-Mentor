export type Role = "user" | "assistant";
export type Confidence = "sufficient" | "insufficient" | "error";

export interface ChatMessage {
  role: Role;
  content: string;
}

export interface Citation {
  chapter: number;
  verse: string;
  type: string;
  chunk_id: string;
  source_pages: number[];
  preview?: string;
  score?: number;
}

export interface RetrievedChunk {
  chunk_id: string;
  chapter: number;
  verse: string;
  type: string;
  text: string;
  score: number;
  source_pages: number[];
}

export interface ChatResponse {
  request_id: string;
  answer: string;
  intent?: string;
  theme?: string;
  citations: Citation[];
  retrieved_chunks: RetrievedChunk[];
  confidence: Confidence;
  warnings: string[];
  provider: {
    embedding: string;
    llm: string;
  };
}

export interface UiMessage {
  id: string;
  role: Role;
  content: string;
  response?: ChatResponse;
  status?: "thinking" | "streaming" | "failed";
}

export interface ChatSession {
  id: string;
  user_id: string;
  title: string;
  summary?: string;
  created_at: string;
  updated_at: string;
}

export interface StoredMessage {
  id: number;
  session_id: string;
  role: Role;
  content: string;
  request_id?: string;
  response?: ChatResponse;
  timestamp: string;
}

export interface StreamThinkingEvent {
  type: "thinking";
}

export interface StreamTokenEvent {
  type: "token";
  token: string;
  content: string;
}

export interface StreamDoneEvent {
  type: "done";
  response: ChatResponse;
}

export interface StreamErrorEvent {
  type: "error";
  message: string;
}

export type ChatStreamEvent =
  | StreamThinkingEvent
  | StreamTokenEvent
  | StreamDoneEvent
  | StreamErrorEvent;
