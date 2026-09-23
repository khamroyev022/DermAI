import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { documentsApi } from "../api/documents";
import { chatsApi } from "../api/chats";
import { useAuth } from "../hooks/useAuth";
import StatusBadge from "../components/StatusBadge";
import { formatDate } from "../lib/format";

export default function DashboardPage() {
  const { user } = useAuth();
  const documents = useQuery({ queryKey: ["documents"], queryFn: documentsApi.list, refetchInterval: 5000 });
  const chats = useQuery({ queryKey: ["chats", "all"], queryFn: () => chatsApi.list() });

  const docs = documents.data ?? [];
  const counts = {
    total: docs.length,
    ready: docs.filter((d) => d.status === "READY").length,
    processing: docs.filter((d) => d.status === "PROCESSING" || d.status === "UPLOADED").length,
    failed: docs.filter((d) => d.status === "FAILED").length,
  };

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-8">
      <h1 className="text-2xl font-semibold text-slate-900">Hello, {user?.username} 👋</h1>
      <p className="mt-1 text-sm text-slate-500">Upload a PDF book, wait for it to become READY, then ask questions.</p>

      <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        {[
          { label: "Documents", value: counts.total },
          { label: "Ready", value: counts.ready },
          { label: "Processing", value: counts.processing },
          { label: "Chats", value: chats.data?.length ?? 0 },
        ].map((item) => (
          <div key={item.label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{item.label}</p>
            <p className="mt-1 text-3xl font-semibold text-slate-900">{item.value}</p>
          </div>
        ))}
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">Recent documents</h2>
            <Link to="/documents" className="text-sm font-medium text-indigo-600 hover:underline">
              Manage
            </Link>
          </div>
          <ul className="mt-3 divide-y divide-slate-100">
            {docs.slice(0, 6).map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-3 py-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-800">{d.title}</p>
                  <p className="text-xs text-slate-500">{formatDate(d.created_at)}</p>
                </div>
                <StatusBadge status={d.status} progress={d.processing_progress} />
              </li>
            ))}
            {docs.length === 0 && !documents.isLoading && (
              <li className="py-4 text-sm text-slate-500">
                No documents yet.{" "}
                <Link to="/documents" className="font-medium text-indigo-600 hover:underline">
                  Upload your first PDF
                </Link>
                .
              </li>
            )}
          </ul>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">Recent chats</h2>
            <Link to="/chat" className="text-sm font-medium text-indigo-600 hover:underline">
              Open chat
            </Link>
          </div>
          <ul className="mt-3 divide-y divide-slate-100">
            {(chats.data ?? []).slice(0, 6).map((c) => (
              <li key={c.id} className="py-2">
                <Link to={`/chat/${c.id}`} className="block">
                  <p className="truncate text-sm font-medium text-slate-800">{c.title || `Chat ${c.id}`}</p>
                  <p className="text-xs text-slate-500">
                    {c.document.title} · {c.message_count} messages · {formatDate(c.updated_at)}
                  </p>
                </Link>
              </li>
            ))}
            {(chats.data ?? []).length === 0 && !chats.isLoading && (
              <li className="py-4 text-sm text-slate-500">No conversations yet.</li>
            )}
          </ul>
        </section>
      </div>

      {counts.failed > 0 && (
        <p className="mt-6 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {counts.failed} document(s) failed to process. Open the Documents page for details.
        </p>
      )}
    </div>
  );
}
