import type { ChatSession, Document } from "../types";

interface Props {
  documents: Document[];
  selectedDocumentId: number | null;
  onSelectDocument: (id: number) => void;
  chats: ChatSession[];
  activeChatId: number | null;
  onSelectChat: (id: number) => void;
  onNewChat: () => void;
  onDeleteChat: (id: number) => void;
  creating?: boolean;
}

export default function ChatSidebar({
  documents,
  selectedDocumentId,
  onSelectDocument,
  chats,
  activeChatId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
  creating,
}: Props) {
  const readyDocuments = documents.filter((d) => d.status === "READY");

  return (
    <aside className="flex h-full w-full flex-col border-r border-slate-200 bg-slate-50 md:w-72">
      <div className="border-b border-slate-200 p-3">
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Document</label>
        <select
          value={selectedDocumentId ?? ""}
          onChange={(e) => onSelectDocument(Number(e.target.value))}
          className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
        >
          <option value="" disabled>
            {readyDocuments.length ? "Select a book…" : "No READY documents yet"}
          </option>
          {readyDocuments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.title}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!selectedDocumentId || creating}
          onClick={onNewChat}
          className="mt-2 w-full rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {creating ? "Creating…" : "+ New chat"}
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        <p className="px-2 pb-1 pt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Chat history</p>
        {chats.length === 0 && <p className="px-2 py-3 text-sm text-slate-500">No chats yet for this document.</p>}
        <ul className="space-y-1">
          {chats.map((chat) => (
            <li key={chat.id} className="group flex items-center gap-1">
              <button
                type="button"
                onClick={() => onSelectChat(chat.id)}
                className={`min-w-0 flex-1 truncate rounded-md px-2 py-1.5 text-left text-sm ${
                  chat.id === activeChatId ? "bg-white font-medium text-slate-900 shadow-sm" : "text-slate-700 hover:bg-slate-200"
                }`}
                title={chat.title}
              >
                {chat.title || `Chat ${chat.id}`}
              </button>
              <button
                type="button"
                onClick={() => onDeleteChat(chat.id)}
                className="rounded px-1.5 py-1 text-xs text-slate-400 opacity-0 hover:bg-rose-50 hover:text-rose-600 group-hover:opacity-100"
                title="Delete chat"
                aria-label="Delete chat"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
