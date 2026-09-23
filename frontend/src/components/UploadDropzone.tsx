import { useCallback, useRef, useState, type DragEvent } from "react";

interface Props {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
  maxSizeMb?: number;
}

export default function UploadDropzone({ onFiles, disabled, maxSizeMb = 100 }: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = useCallback(
    (list: FileList | null) => {
      if (!list || disabled) return;
      const files = Array.from(list).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
      if (files.length) onFiles(files);
    },
    [onFiles, disabled],
  );

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    accept(event.dataTransfer.files);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition ${
        dragging ? "border-indigo-500 bg-indigo-50" : "border-slate-300 bg-white hover:border-slate-400"
      } ${disabled ? "pointer-events-none opacity-60" : ""}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        className="hidden"
        onChange={(e) => {
          accept(e.target.files);
          e.target.value = "";
        }}
      />
      <div className="text-4xl">📄</div>
      <p className="mt-3 text-base font-medium text-slate-800">Drag &amp; drop PDF books here</p>
      <p className="mt-1 text-sm text-slate-500">or click to choose files · PDF only · up to {maxSizeMb} MB each</p>
    </div>
  );
}
