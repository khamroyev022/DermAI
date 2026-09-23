import { useState } from "react";
import type { Document } from "../types";
import { formatBytes, formatDate } from "../lib/format";
import StatusBadge from "./StatusBadge";

interface Props {
  document: Document;
  onChat: (document: Document) => void;
  onDelete: (document: Document) => Promise<void> | void;
  deleting?: boolean;
}

export default function DocumentRow({ document, onChat, onDelete, deleting }: Props) {
  const [confirming, setConfirming] = useState(false);
  const ready = document.status === "READY";

  return (
    <li className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate text-base font-semibold text-slate-900" title={document.title}>
            {document.title}
          </h3>
          <StatusBadge status={document.status} progress={document.processing_progress} />
        </div>
        <p className="mt-1 truncate text-sm text-slate-500" title={document.original_filename}>
          {document.original_filename}
        </p>
        <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
          <div>
            <dt className="inline font-medium text-slate-600">Pages: </dt>
            <dd className="inline">{document.page_count}</dd>
          </div>
          <div>
            <dt className="inline font-medium text-slate-600">Size: </dt>
            <dd className="inline">{formatBytes(document.file_size)}</dd>
          </div>
          <div>
            <dt className="inline font-medium text-slate-600">Uploaded: </dt>
            <dd className="inline">{formatDate(document.created_at)}</dd>
          </div>
        </dl>
        {document.status === "PROCESSING" && (
          <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
            <div className="h-full bg-amber-500 transition-all" style={{ width: `${document.processing_progress}%` }} />
          </div>
        )}
        {document.status === "FAILED" && document.processing_error && (
          <p className="mt-2 rounded-md bg-rose-50 px-2 py-1 text-xs text-rose-700">{document.processing_error}</p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          disabled={!ready}
          onClick={() => onChat(document)}
          className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          title={ready ? "Chat with this book" : "Available once processing is finished"}
        >
          Chat
        </button>
        {confirming ? (
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={deleting}
              onClick={async () => {
                await onDelete(document);
                setConfirming(false);
              }}
              className="rounded-md bg-rose-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-60"
            >
              {deleting ? "Deleting…" : "Confirm"}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="rounded-md border border-rose-300 px-3 py-1.5 text-sm font-medium text-rose-700 hover:bg-rose-50"
          >
            Delete
          </button>
        )}
      </div>
    </li>
  );
}
