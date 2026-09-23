import { useEffect } from "react";
import type { Source } from "../types";
import { pageLabel } from "../lib/format";

interface Props {
  source: Source | null;
  documentTitle?: string;
  onClose: () => void;
}

export default function SourceModal({ source, documentTitle, onClose }: Props) {
  useEffect(() => {
    if (!source) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [source, onClose]);

  if (!source) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="max-h-[80vh] w-full max-w-2xl overflow-hidden rounded-xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Source excerpt</p>
            <h2 className="mt-1 text-base font-semibold text-slate-900">
              {documentTitle ? `${documentTitle} · ` : ""}
              {pageLabel(source.page_start, source.page_end)}
            </h2>
            {typeof source.score === "number" && (
              <p className="mt-0.5 text-xs text-slate-500">Similarity {(source.score * 100).toFixed(0)}%</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <div className="max-h-[60vh] overflow-y-auto px-5 py-4 text-sm leading-relaxed text-slate-800 prose-answer">
          {source.excerpt}
        </div>
      </div>
    </div>
  );
}
