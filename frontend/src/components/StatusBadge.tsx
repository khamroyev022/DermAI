import type { DocumentStatus } from "../types";

interface Props {
  status: DocumentStatus;
  progress?: number;
}

const styles: Record<DocumentStatus, string> = {
  UPLOADED: "bg-slate-100 text-slate-700 ring-slate-300",
  PROCESSING: "bg-amber-50 text-amber-800 ring-amber-300",
  READY: "bg-emerald-50 text-emerald-700 ring-emerald-300",
  FAILED: "bg-rose-50 text-rose-700 ring-rose-300",
};

export default function StatusBadge({ status, progress = 0 }: Props) {
  const label =
    status === "PROCESSING"
      ? `Processing ${progress}%`
      : status === "UPLOADED"
        ? "Queued"
        : status === "READY"
          ? "READY"
          : "FAILED";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${styles[status]}`}>
      {status === "PROCESSING" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />}
      {label}
    </span>
  );
}
