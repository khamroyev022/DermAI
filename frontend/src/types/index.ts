export type DocumentStatus = "UPLOADED" | "PROCESSING" | "READY" | "FAILED";

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  date_joined: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface RegisterResponse extends AuthTokens {
  user: User;
}

export interface Document {
  id: number;
  title: string;
  original_filename: string;
  file_size: number;
  sha256: string;
  page_count: number;
  status: DocumentStatus;
  processing_progress: number;
  processing_error: string;
  created_at: string;
  updated_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ChatDocument {
  id: number;
  title: string;
  status: DocumentStatus;
  page_count: number;
}

export interface Source {
  chunk_id: number;
  page_start: number;
  page_end: number;
  score?: number;
  excerpt: string;
}

export type MessageRole = "USER" | "ASSISTANT";

export interface ChatMessage {
  id: number;
  role: MessageRole;
  content: string;
  sources: Source[];
  created_at: string;
}

export interface ChatSession {
  id: number;
  title: string;
  document: ChatDocument;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export interface SendMessageResponse {
  answer: string;
  sources: Source[];
  document: ChatDocument;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
}
