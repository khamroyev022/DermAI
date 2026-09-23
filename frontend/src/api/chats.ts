import { api } from "./client";
import type { ChatSession, ChatSessionDetail, Paginated, SendMessageResponse } from "../types";

export const chatsApi = {
  async list(documentId?: number): Promise<ChatSession[]> {
    const { data } = await api.get<Paginated<ChatSession>>("/chats/", {
      params: { page_size: 100, ...(documentId ? { document: documentId } : {}) },
    });
    return data.results;
  },
  async create(documentId: number, title?: string): Promise<ChatSession> {
    const { data } = await api.post<ChatSession>("/chats/", { document_id: documentId, title });
    return data;
  },
  async get(id: number): Promise<ChatSessionDetail> {
    const { data } = await api.get<ChatSessionDetail>(`/chats/${id}/`);
    return data;
  },
  async remove(id: number): Promise<void> {
    await api.delete(`/chats/${id}/`);
  },
  async sendMessage(id: number, message: string): Promise<SendMessageResponse> {
    const { data } = await api.post<SendMessageResponse>(`/chats/${id}/messages/`, { message }, { timeout: 180_000 });
    return data;
  },
};
