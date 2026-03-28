"use client";

import React from "react";
import { useAppContext } from "@/context/AppContext";
import { Loader2, CheckCircle2, AlertCircle, X } from "lucide-react";
import { IngestionJob } from "@/lib/api";

export const BackgroundTasks = () => {
  const { activeJobs, removeJob } = useAppContext();
  const jobIds = Object.keys(activeJobs);

  if (jobIds.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 mt-auto pt-4 border-t border-[var(--color-border)]">
      <h3 className="text-[10px] uppercase font-bold text-[var(--color-muted)] tracking-[0.1em]">Background Tasks</h3>
      <div className="flex flex-col gap-2 max-h-48 overflow-y-auto pr-1 no-scrollbar">
        {jobIds.map((id) => (
          <JobItem key={id} job={activeJobs[id]} onRemove={() => removeJob(id)} />
        ))}
      </div>
    </div>
  );
};

const JobItem = ({ job, onRemove }: { job: IngestionJob; onRemove: () => void }) => {
  const isComplete = job.status === "complete";
  const isError = job.status === "error";
  const lastProgress = job.progress.length > 0 ? job.progress[job.progress.length - 1] : null;
  const stage = lastProgress?.stage || (job.status === "queued" ? "Queued" : job.status === "error" ? "Failed" : job.status === "complete" ? "Story Ready" : "Running");
  const detail = lastProgress?.progress || (job.status === "queued" ? "Waiting for ingestion to start" : "Processing document");
  const stepText = lastProgress?.step && lastProgress?.total_steps
    ? `Step ${lastProgress.step}/${lastProgress.total_steps}`
    : job.status === "queued"
      ? "Step 0/6"
      : null;
  const progressPercent = isComplete
    ? 100
    : Math.max(lastProgress?.progress_percent ?? 0, job.status === "queued" ? 6 : 10);

  return (
    <div className="glass-pill rounded-lg p-2.5 flex flex-col gap-2 text-[11px] group transition-premium hover:bg-[var(--color-surface-hover)]">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 overflow-hidden">
          {isComplete ? (
            <CheckCircle2 className="w-3 h-3 text-[var(--color-success)] shrink-0" />
          ) : isError ? (
            <AlertCircle className="w-3 h-3 text-[var(--color-error)] shrink-0" />
          ) : (
            <Loader2 className="w-3 h-3 text-[var(--color-primary)] animate-spin shrink-0" />
          )}
          <span className="font-medium truncate text-[var(--text-primary)]">{job.filename}</span>
        </div>
        <button 
          onClick={onRemove}
          className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-[var(--color-error)]/10 hover:text-[var(--color-error)] rounded transition-premium cursor-pointer active:scale-95"
        >
          <X className="w-3 h-3" />
        </button>
      </div>

      {!isError && (
        <div className="flex flex-col gap-1.5 pl-4.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--color-muted)]">
              {stage}
            </span>
            {stepText && (
              <span className="text-[10px] text-[var(--color-muted)]">
                {stepText}
              </span>
            )}
          </div>
          <div className="text-[var(--text-secondary)] leading-tight min-h-[28px]">
            {detail}
          </div>
          <div className="w-full h-2 bg-[var(--surface-secondary)] rounded-full overflow-hidden border border-[var(--color-border)] shadow-inner">
            <div
              className="h-full bg-[var(--color-primary)] relative transition-all duration-500 ease-out shadow-[0_0_15px_rgba(0,112,243,0.4)]"
              style={{ width: `${progressPercent}%` }}
            >
              <div className="absolute inset-0 shimmer opacity-40 mix-blend-overlay" />
            </div>
          </div>
          <div className="flex justify-between items-center text-[10px] text-[var(--color-muted)] font-bold">
            <span className="text-[var(--color-primary)]">{progressPercent}%</span>
            {lastProgress?.timestamp && (
              <span className="opacity-60">{new Date(lastProgress.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
            )}
          </div>
        </div>
      )}

      {isError && (
        <div className="pl-4.5 text-[var(--color-error)] leading-tight">
          {job.error || "Failed to process document"}
        </div>
      )}
    </div>
  );
};
