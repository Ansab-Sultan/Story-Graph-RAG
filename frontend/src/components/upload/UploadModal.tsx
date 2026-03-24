"use client";
import React, { useState, useRef, useEffect } from "react";
import { X, UploadCloud, FileText, CheckCircle2, Loader2 } from "lucide-react";
import { useAppContext } from "@/context/AppContext";
import clsx from "clsx";

export const UploadModal = ({ onClose }: { onClose: () => void }) => {
  const { refreshStories } = useAppContext();
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [progressLog]);

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/stories", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Upload failed");
      }

      const data = await res.json();
      const storyId = data.story_id;

      // Start SSE
      const eventSource = new EventSource(`/api/stories/${storyId}/stream`);

      eventSource.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          setProgressLog((prev) => [...prev, `[${parsed.node}] ${parsed.progress}`]);
        } catch (e) {
          setProgressLog((prev) => [...prev, event.data]);
        }
      };

      eventSource.onerror = (err) => {
        console.error("SSE Error", err);
      };

      // Poll completion 
      const checkCompletion = setInterval(async () => {
        try {
          const statRes = await fetch(`/api/stories/${storyId}`);
          if (statRes.ok) {
            const statData = await statRes.json();
            if (statData.status === "complete") {
              clearInterval(checkCompletion);
              eventSource.close();
              setIsComplete(true);
              setIsUploading(false);
              refreshStories();
            }
          }
        } catch (e) {}
      }, 3000);

    } catch (err: any) {
      setError(err.message);
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 text-[var(--foreground)]">
      <div className="bg-[var(--color-surface)] w-full max-w-lg rounded-xl shadow-2xl overflow-hidden border border-[var(--color-border)] flex flex-col max-h-[90vh]">
        <div className="flex justify-between items-center p-4 border-b border-[var(--color-border)]">
          <h2 className="text-xl font-bold tracking-tight">Upload Story</h2>
          <button onClick={onClose} disabled={isUploading && !isComplete} className="text-gray-500 hover:text-[var(--foreground)]">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 flex flex-col gap-6 overflow-y-auto">
          {!isUploading && !isComplete && (
            <>
              {error && <div className="text-red-500 text-sm bg-red-50 dark:bg-red-900/20 p-3 rounded-md border border-red-200">{error}</div>}
              
              <div className="border-2 border-dashed border-[var(--color-border)] rounded-xl p-8 flex flex-col items-center text-center gap-4 bg-[var(--background)]">
                <UploadCloud className="w-12 h-12 text-gray-400" />
                <div>
                  <label className="cursor-pointer text-[var(--color-primary)] font-medium hover:underline">
                    Browse for a file
                    <input 
                      type="file" 
                      accept=".pdf,.txt" 
                      className="hidden" 
                      onChange={(e) => e.target.files && setFile(e.target.files[0])}
                    />
                  </label>
                  <p className="text-sm text-gray-500 mt-1">.pdf or .txt formats only.</p>
                </div>
                {file && (
                  <div className="flex items-center gap-2 bg-[var(--color-surface-hover)] px-3 py-2 rounded-md border border-[var(--color-border)] mt-2">
                    <FileText className="w-4 h-4 text-[var(--color-secondary)]" />
                    <span className="text-sm font-medium">{file.name}</span>
                    <button onClick={() => setFile(null)} className="ml-2 text-gray-400 hover:text-[var(--foreground)]"><X className="w-4 h-4"/></button>
                  </div>
                )}
              </div>
              
              <button 
                onClick={handleUpload}
                disabled={!file}
                className={clsx(
                  "py-3 rounded-lg font-medium transition-colors w-full",
                  file ? "bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)] shadow-md" : "bg-gray-100 dark:bg-slate-800 text-gray-400 cursor-not-allowed border border-[var(--color-border)]"
                )}
              >
                Upload and Ingest
              </button>
            </>
          )}

          {(isUploading || isComplete) && (
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-3">
                {isComplete ? (
                  <CheckCircle2 className="w-6 h-6 text-green-500" />
                ) : (
                  <Loader2 className="w-6 h-6 text-[var(--color-primary)] animate-spin" />
                )}
                <h3 className="font-semibold">{isComplete ? "Ingestion Complete!" : "Processing Document..."}</h3>
              </div>
              
              <div className="bg-slate-900 dark:bg-black text-green-400 text-xs font-mono p-4 rounded-lg h-64 overflow-y-auto whitespace-pre-wrap leading-relaxed shadow-inner border border-slate-800">
                {progressLog.map((log, i) => (
                  <div key={i}>{log}</div>
                ))}
                {!isComplete && (
                  <div className="animate-pulse">_</div>
                )}
                <div ref={bottomRef} />
              </div>

              {isComplete && (
                <button 
                  onClick={onClose}
                  className="mt-2 py-3 bg-[var(--color-primary)] text-white rounded-lg font-medium hover:bg-[var(--color-primary-hover)] w-full shadow-md"
                >
                  Return to Library
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
