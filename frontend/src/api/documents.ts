import { api } from "./client";
import type { Document, Paginated } from "../types";

export const documentsApi = {
  async list(): Promise<Document[]> {
    const { data } = await api.get<Paginated<Document>>("/documents/", { params: { page_size: 100 } });
    return data.results;
  },
  async get(id: number): Promise<Document> {
    const { data } = await api.get<Document>(`/documents/${id}/`);
    return data;
  },
  async upload(file: File, onProgress?: (percent: number) => void): Promise<Document> {
    const form = new FormData();
    form.append("file", file);
    const { data } = await api.post<Document>("/documents/", form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 0,
      onUploadProgress: (event) => {
        if (onProgress && event.total) onProgress(Math.round((event.loaded / event.total) * 100));
      },
    });
    return data;
  },
  async remove(id: number): Promise<void> {
    await api.delete(`/documents/${id}/`);
  },
};
