import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { chatsApi } from "../api/chats";
import { documentsApi } from "../api/documents";
import { getErrorMessage } from "../api/client";
import ChatSidebar from "../components/ChatSidebar";
import MessageBubble from "../components/MessageBubble";
import SourceModal from "../components/SourceModal";
import type { ChatMessage, ChatSessionDetail, Source } from "../types";

export default function ChatPage() {
  const { chatId } = useParams();
  const activeChatId = chatId ? Number(chatId) : null;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const documents = useQuery({ queryKey: ["documents"], queryFn: documentsApi.list });
  const chat = useQuery({
    queryKey: ["chats", activeChatId],
    queryFn: () => chatsApi.get(activeChatId as number),
    enabled: activeChatId !== null,
  });

  // Keep the sidebar's document selector in sync with the open chat.
  useEffect(() => {
    if (chat.data) setSelectedDocumentId(chat.data.document.id);
  }, [chat.data]);

  // Default to the first READY document when nothing is selected.
  useEffect(() => {
    if (selectedDocumentId === null && documents.data) {
      const first = documents.data.find((d) => d.status === "READY");
      if (first) setSelectedDocumentId(first.id);
    }
  }, [documents.data, selectedDocumentId]);

  const chats = useQuery({
    queryKey: ["chats", "document", selectedDocumentId],
    queryFn: () => chatsApi.list(selectedDocumentId as number),
    enabled: selectedDocumentId !== null,
  });

  const createChat = useMutation({
    mutationFn: () => chatsApi.create(selectedDocumentId as number),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["chats"] });
      navigate(`/chat/${created.id}`);
    },
    onError: (err) => setError(getErrorMessage(err, "Could not create the chat.")),
  });

  const deleteChat = useMutation({
    mutationFn: (id: number) => chatsApi.remove(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["chats"] });
      if (id === activeChatId) navigate("/chat");
    },
    onError: (err) => setError(getErrorMessage(err, "Could not delete the chat.")),
  });

  const sendMessage = useMutation({
    mutationFn: (message: string) => chatsApi.sendMessage(activeChatId as number, message),
    onMutate: async (message) => {
      setError(null);
      const key = ["chats", activeChatId];
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<ChatSessionDetail>(key);
      const optimistic: ChatMessage = {
        id: -Date.now(),
        role: "USER",
        content: message,
        sources: [],
        created_at: new Date().toISOString(),
      };
      if (previous) {
        queryClient.setQueryData<ChatSessionDetail>(key, { ...previous, messages: [...previous.messages, optimistic] });
      }
      return { previous };
    },
    onSuccess: (response) => {
      const key = ["chats", activeChatId];
      queryClient.setQueryData<ChatSessionDetail>(key, (current) => {
        if (!current) return current;
        const withoutOptimistic = current.messages.filter((m) => m.id > 0);
        return {
          ...current,
          title: current.messages.length === 0 ? response.user_message.content : current.title,
          messages: [...withoutOptimistic, response.user_message, response.assistant_message],
        };
      });
      queryClient.invalidateQueries({ queryKey: ["chats", "document", selectedDocumentId] });
    },
    onError: (err, _message, context) => {
      if (context?.previous) queryClient.setQueryData(["chats", activeChatId], context.previous);
      setError(getErrorMessage(err, "The assistant could not answer."));
    },
  });

  const messages = chat.data?.messages ?? [];
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, sendMessage.isPending]);

  const submit = () => {
    const text = draft.trim();
    if (!text || !activeChatId || sendMessage.isPending) return;
    setDraft("");
    sendMessage.mutate(text);
    textareaRef.current?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  const documentTitle = useMemo(() => chat.data?.document.title, [chat.data]);
  const chatReady = chat.data?.document.status === "READY";

  return (
    <div className="flex min-h-0 flex-1 flex-col md:flex-row">
      <ChatSidebar
        documents={documents.data ?? []}
        selectedDocumentId={selectedDocumentId}
        onSelectDocument={(id) => {
          setSelectedDocumentId(id);
          navigate("/chat");
        }}
        chats={chats.data ?? []}
        activeChatId={activeChatId}
        onSelectChat={(id) => navigate(`/chat/${id}`)}
        onNewChat={() => createChat.mutate()}
        onDeleteChat={(id) => deleteChat.mutate(id)}
        creating={createChat.isPending}
      />

      <section className="flex min-h-0 flex-1 flex-col bg-slate-100">
        {activeChatId === null ? (
          <div className="flex flex-1 flex-col items-center justify-center px-6 text-center text-slate-500">
            <div className="text-5xl">💬</div>
            <p className="mt-3 text-base font-medium text-slate-700">Pick a READY book and start a new chat</p>
            <p className="mt-1 max-w-md text-sm">
              Answers use only the selected document. If the answer is not in the book, the assistant says so.
            </p>
          </div>
        ) : (
          <>
            <div className="border-b border-slate-200 bg-white px-4 py-2 text-sm">
              <span className="font-medium text-slate-800">{documentTitle ?? "Loading…"}</span>
              {chat.data && <span className="ml-2 text-slate-500">· {chat.data.document.page_count} pages</span>}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
              <div className="mx-auto flex max-w-3xl flex-col gap-3">
                {chat.isLoading && <p className="text-sm text-slate-500">Loading conversation…</p>}
                {chat.isError && (
                  <p className="text-sm text-rose-600">{getErrorMessage(chat.error, "Could not load the chat.")}</p>
                )}
                {messages.length === 0 && chat.data && (
                  <p className="text-center text-sm text-slate-500">Ask anything about “{documentTitle}”.</p>
                )}
                {messages.map((m) => (
                  <MessageBubble key={m.id} message={m} onSourceClick={setActiveSource} />
                ))}
                {sendMessage.isPending && (
                  <div className="flex justify-start">
                    <div className="rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
                      <span className="animate-pulse">Searching the book and thinking…</span>
                    </div>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            </div>

            <div className="border-t border-slate-200 bg-white px-4 py-3">
              <div className="mx-auto max-w-3xl">
                {error && <p className="mb-2 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
                {!chatReady && chat.data && (
                  <p className="mb-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
                    This document is not READY yet.
                  </p>
                )}
                <div className="flex items-end gap-2">
                  <textarea
                    ref={textareaRef}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={onKeyDown}
                    rows={1}
                    placeholder="Ask a question… (Enter to send, Shift+Enter for a new line)"
                    disabled={!chatReady || sendMessage.isPending}
                    className="max-h-48 min-h-[44px] flex-1 resize-none rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:border-indigo-500 focus:outline-none disabled:bg-slate-100"
                  />
                  <button
                    type="button"
                    onClick={submit}
                    disabled={!draft.trim() || !chatReady || sendMessage.isPending}
                    className="h-[44px] rounded-xl bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    Send
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </section>

      <SourceModal source={activeSource} documentTitle={documentTitle} onClose={() => setActiveSource(null)} />
    </div>
  );
}
