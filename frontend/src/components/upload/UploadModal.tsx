"use client";
import React, { useState } from "react";
import { X, UploadCloud, FileText, Loader2 } from "lucide-react";
import { useAppContext } from "@/context/AppContext";
import clsx from "clsx";

export const UploadModal = ({ onClose }: { onClose: () => void }) => {
  const { startIngestion } = useAppContext();
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      
      // Initiate background ingestion via context
      startIngestion(data.story_id, file.name);
      
      // Close modal immediately
      onClose();
    } catch (err: any) {
      setError(err.message);
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-md p-4 transition-premium">
      <div className="glass-panel w-full max-w-lg rounded-3xl overflow-hidden flex flex-col max-h-[90vh] shadow-[0_32px_64px_-12px_rgba(0,0,0,0.6)] animate-in fade-in zoom-in duration-300">
        <div className="flex justify-between items-center p-6 border-b border-[var(--color-border)]">
          <div>
            <h2 className="text-xl font-bold tracking-tight">Ingest Narrative</h2>
            <p className="text-xs text-[var(--color-muted)] mt-1">Upload a PDF or TXT to generate a knowledge graph.</p>
          </div>
          <button 
            onClick={onClose} 
            disabled={isUploading} 
            className="text-[var(--color-muted)] hover:text-[var(--foreground)] transition-premium hover:rotate-90 p-2 rounded-full hover:bg-[var(--color-surface-hover)] cursor-pointer disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-8 flex flex-col gap-8">
          {error && (
            <div className="text-red-400 text-sm bg-red-400/10 p-4 rounded-2xl border border-red-400/20 flex items-center gap-3">
              <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
              {error}
            </div>
          )}
          
          <div className="group relative">
            <div className="absolute -inset-1 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-secondary)] rounded-2xl blur opacity-10 group-hover:opacity-20 transition-premium" />
            <div className="relative border-2 border-dashed border-[var(--color-border)] rounded-2xl p-10 flex flex-col items-center text-center gap-4 bg-[var(--color-surface)]/50 group-hover:border-[var(--color-primary)]/50 transition-premium cursor-pointer">
              <div className="w-16 h-16 rounded-2xl bg-[var(--color-primary)]/10 flex items-center justify-center text-[var(--color-primary)] mb-2">
                <UploadCloud className="w-8 h-8" />
              </div>
              <div className="space-y-1">
                <p className="font-semibold text-lg">Drop your story here</p>
                <p className="text-sm text-[var(--color-muted)]">Support for high-density PDF or TXT files</p>
              </div>
              <label className="cursor-pointer">
                <span className="text-white bg-[var(--color-primary)] px-5 py-2.5 rounded-xl font-bold hover:bg-[var(--color-primary-hover)] transition-premium shadow-lg shadow-[var(--color-primary)]/20 block mt-2 hover:-translate-y-0.5 active:scale-[0.98]">
                  Select File
                </span>
                <input 
                  type="file" 
                  accept=".pdf,.txt" 
                  className="hidden" 
                  onChange={(e) => e.target.files && setFile(e.target.files[0])}
                />
              </label>
            </div>
          </div>

          {file && (
            <div className="flex items-center gap-4 bg-[var(--color-surface)] p-4 rounded-2xl border border-[var(--color-border)] shadow-sm animate-in slide-in-from-bottom-4 duration-300">
              <div className="w-10 h-10 rounded-xl bg-[var(--color-secondary)]/10 flex items-center justify-center text-[var(--color-secondary)]">
                <FileText className="w-5 h-5" />
              </div>
              <div className="flex-1 overflow-hidden">
                <p className="text-sm font-semibold truncate">{file.name}</p>
                <p className="text-[10px] text-[var(--color-muted)]">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
              <button 
                onClick={() => setFile(null)} 
                className="text-[var(--color-muted)] hover:text-[var(--color-error)] transition-premium p-1.5 rounded-lg hover:bg-[var(--color-error)]/10 cursor-pointer"
              >
                <X className="w-4 h-4"/>
              </button>
            </div>
          )}
          
          <button 
            onClick={handleUpload}
            disabled={!file || isUploading}
            className={clsx(
              "py-4 rounded-2xl font-bold transition-premium w-full flex items-center justify-center gap-3 text-lg shadow-xl",
              file && !isUploading 
                ? "bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)] hover:scale-[1.02] active:scale-[0.98] cursor-pointer shadow-[var(--color-primary)]/10" 
                : "bg-[var(--surface-secondary)] text-[var(--color-muted)] cursor-not-allowed border border-[var(--color-border)] shadow-none"
            )}
          >
            {isUploading ? (
              <>
                <Loader2 className="w-6 h-6 animate-spin" />
                <span>Processing Stream...</span>
              </>
            ) : (
              <span>Start Ingestion</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
