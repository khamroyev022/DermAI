import type { ChatMessage, Source } from "../types";
import { pageLabel } from "../lib/format";

interface Props {
  message: ChatMessage;
  onSourceClick: (source: Source) => void;
}

export default function MessageBubble({ message, onSourceClick }: Props) {
  const isUser = message.role === "USER";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm md:max-w-[75%] ${
          isUser ? "rounded-br-sm bg-indigo-600 text-white" : "rounded-bl-sm border border-slate-200 bg-white text-slate-900"
        }`}
      >
        <div className="prose-answer">{message.content}</div>
        {!isUser && message.sources?.length > 0 && (
          <div className="mt-3 border-t border-slate-200 pt-2">
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Sources</p>
            <div className="flex flex-wrap gap-1.5">
              {message.sources.map((source) => (
                <button
                  key={source.chunk_id}
                  type="button"
                  onClick={() => onSourceClick(source)}
                  className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                  title="Show excerpt"
                >
                  {pageLabel(source.page_start, source.page_end)}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
