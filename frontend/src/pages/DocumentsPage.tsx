import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { documentsApi } from "../api/documents";
import { chatsApi } from "../api/chats";
import { getErrorMessage } from "../api/client";
import DocumentRow from "../components/DocumentRow";
import UploadDropzone from "../components/UploadDropzone";
import type { Document } from "../types";

interface UploadState {
  id: string;
  name: string;
  percent: number;
  error?: string;
  done?: boolean;
}

export default function DocumentsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [uploads, setUploads] = useState<UploadState[]>([]);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: documentsApi.list,
    // Poll while anything is still processing so the progress % updates live.
    refetchInterval: (query) => {
      const data = query.state.data as Document[] | undefined;
      return data?.some((d) => d.status === "PROCESSING" || d.status === "UPLOADED") ? 2000 : false;
    },
  });

  const removeMutation = useMutation({
    mutationFn: (id: number) => documentsApi.remove(id),
    onMutate: (id) => setDeletingId(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["chats"] });
    },
    onError: (err) => setError(getErrorMessage(err, "Could not delete the document.")),
    onSettled: () => setDeletingId(null),
  });

  const uploadFiles = useCallback(
    async (files: File[]) => {
      setError(null);
      for (const file of files) {
        const id = `${file.name}-${Date.now()}-${Math.random()}`;
        setUploads((prev) => [...prev, { id, name: file.name, percent: 0 }]);
        try {
          await documentsApi.upload(file, (percent) =>
            setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, percent } : u))),
          );
          setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, percent: 100, done: true } : u)));
          queryClient.invalidateQueries({ queryKey: ["documents"] });
          setTimeout(() => setUploads((prev) => prev.filter((u) => u.id !== id)), 2500);
        } catch (err) {
          setUploads((prev) =>
            prev.map((u) => (u.id === id ? { ...u, error: getErrorMessage(err, "Upload failed.") } : u)),
          );
        }
      }
    },
    [queryClient],
  );

  const startChat = async (document: Document) => {
    try {
      const existing = await chatsApi.list(document.id);
      if (existing.length) {
        navigate(`/chat/${existing[0].id}`);
        return;
      }
      const chat = await chatsApi.create(document.id);
      queryClient.invalidateQueries({ queryKey: ["chats"] });
      navigate(`/chat/${chat.id}`);
    } catch (err) {
      setError(getErrorMessage(err, "Could not open a chat."));
    }
  };

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8">
      <h1 className="text-2xl font-semibold text-slate-900">Documents</h1>
      <p className="mt-1 text-sm text-slate-500">
        PDFs are processed in the background: text extraction → chunking → embeddings → vector index.
      </p>

      <div className="mt-6">
        <UploadDropzone onFiles={uploadFiles} maxSizeMb={100} />
      </div>

      {uploads.length > 0 && (
        <ul className="mt-4 space-y-2">
          {uploads.map((u) => (
            <li key={u.id} className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="truncate font-medium text-slate-800">{u.name}</span>
                <span className={`text-xs ${u.error ? "text-rose-600" : "text-slate-500"}`}>
                  {u.error ? "Failed" : u.done ? "Uploaded ✓" : `Uploading ${u.percent}%`}
                </span>
              </div>
              {u.error ? (
                <p className="mt-1 text-xs text-rose-600">{u.error}</p>
              ) : (
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                  <div className="h-full bg-indigo-500 transition-all" style={{ width: `${u.percent}%` }} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {error && <p className="mt-4 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      <section className="mt-8">
        <h2 className="text-base font-semibold text-slate-900">Your library</h2>
        {documents.isLoading && <p className="mt-3 text-sm text-slate-500">Loading…</p>}
        {documents.isError && (
          <p className="mt-3 text-sm text-rose-600">{getErrorMessage(documents.error, "Could not load documents.")}</p>
        )}
        {documents.data && documents.data.length === 0 && (
          <p className="mt-3 text-sm text-slate-500">No documents yet — drop a PDF above to get started.</p>
        )}
        <ul className="mt-3 space-y-3">
          {(documents.data ?? []).map((d) => (
            <DocumentRow
              key={d.id}
              document={d}
              onChat={startChat}
              onDelete={(doc) => removeMutation.mutateAsync(doc.id)}
              deleting={deletingId === d.id}
            />
          ))}
        </ul>
      </section>
    </div>
  );
}
