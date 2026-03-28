"use client";

import React, { useState } from "react";
import { useAppContext } from "@/context/AppContext";
import { BookOpen, CheckCircle2, Clock, Binary, Network, Database, Trash2 } from "lucide-react";
import { ConfirmModal } from "@/components/common/ConfirmModal";
import clsx from "clsx";

export const StorySelector = () => {
  const { stories, selectedStoryId, setSelectedStoryId, deleteStory } = useAppContext();
  const [deleteConfirm, setDeleteConfirm] = useState<{ id: string; title: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  if (stories.length === 0) {
    // ... Vault Empty UI ...
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center px-6 glass-panel rounded-2xl border-dashed">
        <div className="relative mb-4">
           <Database className="w-10 h-10 text-[var(--color-muted)] opacity-20" />
           <div className="absolute inset-0 bg-[var(--color-primary)] blur-2xl opacity-5" />
        </div>
        <p className="text-[11px] text-[var(--color-muted)] font-black uppercase tracking-widest leading-normal">
          Vault Empty
        </p>
        <p className="text-[9px] text-[var(--color-muted)]/60 font-medium mt-1">
          No narrative data indexed.
        </p>
      </div>
    );
  }

  const handleDeleteClick = (e: React.MouseEvent, storyId: string, title: string) => {
    e.stopPropagation();
    setDeleteConfirm({ id: storyId, title });
  };

  const handleConfirmDelete = async () => {
    if (!deleteConfirm) return;
    setIsDeleting(true);
    try {
      await deleteStory(deleteConfirm.id);
      setDeleteConfirm(null);
    } catch (err) {
      console.error(err);
      // We could use a toast here, but for now we'll just log
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="flex flex-col gap-2.5">
      {stories.map((story, index) => {
        const isSelected = selectedStoryId === story.story_id;
        const isProcessing = story.status !== "complete";

        return (
          <div key={story.story_id} className="relative group">
            <button
              onClick={() => setSelectedStoryId(story.story_id)}
              style={{ animationDelay: `${index * 0.1}s` }}
              className={clsx(
                "flex flex-col text-left p-3.5 rounded-xl transition-premium text-sm w-full relative overflow-hidden cursor-pointer stagger-fade-in",
                isSelected
                  ? "bg-[var(--color-primary)]/10 text-[var(--color-primary)] ring-1 ring-[var(--color-primary)]/30 shadow-lg shadow-blue-500/5"
                  : "hover:bg-[var(--color-surface-hover)] border border-transparent hover:border-[var(--color-border)] active:scale-[0.98]"
              )}
            >
              {isSelected && (
                <div className="absolute left-0 top-0 bottom-0 w-1 bg-[var(--color-primary)]" />
              )}

              <div className="flex flex-row items-center gap-2.5 mb-2 pr-8">
                <div className={clsx(
                  "w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-premium",
                  isSelected ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface-hover)] text-[var(--color-muted)] group-hover:text-[var(--foreground)]"
                )}>
                  <BookOpen className="w-4 h-4" />
                </div>
                <span className="font-bold truncate tracking-tight py-1">{story.display_name || story.title}</span>
              </div>

              <div className="grid grid-cols-2 gap-y-2 pl-9">
                <div className="flex items-center gap-1.5 text-[10px] font-medium text-[var(--color-muted)]">
                  {isProcessing ? (
                    <Clock className="w-3 h-3 text-[var(--color-accent)] animate-pulse" />
                  ) : (
                    <CheckCircle2 className="w-3 h-3 text-[var(--color-success)]" />
                  )}
                  <span className="capitalize">{story.status}</span>
                </div>
                
                <div className="flex items-center gap-1.5 text-[10px] font-bold text-[var(--color-muted)]">
                  <Network className="w-3 h-3" />
                  <span>{story.entity_count} Entities</span>
                </div>

                {!isProcessing && (
                  <>
                    <div className="flex items-center gap-1.5 text-[10px] font-bold text-[var(--color-muted)]">
                      <Binary className="w-3 h-3" />
                      <span>{story.chunk_count} Chunks</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-[10px] font-bold text-[var(--color-muted)]">
                      <Database className="w-3 h-3" />
                      <span>{story.relationship_count} Rel</span>
                    </div>
                  </>
                )}
              </div>
            </button>

            <button
              onClick={(e) => handleDeleteClick(e, story.story_id, story.display_name || story.title)}
              className="absolute top-3.5 right-3 p-1.5 rounded-lg text-[var(--color-muted)] hover:text-[var(--color-error)] hover:bg-[var(--color-error)]/10 opacity-0 group-hover:opacity-100 transition-premium cursor-pointer z-10"
              title="Delete Story"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        );
      })}

      <ConfirmModal
        isOpen={!!deleteConfirm}
        title="Purge Sequence"
        message={`Are you sure you want to permanently delete "${deleteConfirm?.title}"? This will terminate all neural links, knowledge graphs, and associated vector data.`}
        confirmLabel={isDeleting ? "Purging..." : "Confirm Purge"}
        cancelLabel="Abort"
        isDestructive={true}
        onConfirm={handleConfirmDelete}
        onCancel={() => !isDeleting && setDeleteConfirm(null)}
      />
    </div>
  );
};
