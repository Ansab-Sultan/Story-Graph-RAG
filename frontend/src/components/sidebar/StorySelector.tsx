"use client";

import React from "react";
import { useAppContext } from "@/context/AppContext";
import { BookOpen, CheckCircle2, Clock } from "lucide-react";
import clsx from "clsx";

export const StorySelector = () => {
  const { stories, selectedStoryId, setSelectedStoryId } = useAppContext();

  if (stories.length === 0) {
    return <div className="text-sm text-gray-500 italic px-2">No stories uploaded yet.</div>;
  }

  return (
    <div className="flex flex-col gap-1">
      {stories.map((story) => (
        <button
          key={story._id}
          onClick={() => setSelectedStoryId(story._id)}
          className={clsx(
            "flex flex-col text-left px-3 py-2 rounded-md transition-colors text-sm w-full group",
            selectedStoryId === story._id
              ? "bg-blue-50/50 dark:bg-blue-900/20 text-[var(--color-primary)] border border-blue-100 dark:border-blue-800"
              : "hover:bg-[var(--color-surface-hover)] border border-transparent"
          )}
        >
          <div className="flex flex-row items-center gap-2">
            <BookOpen className="w-4 h-4 shrink-0" />
            <span className="font-medium truncate">{story.display_name || story.title}</span>
          </div>
          <div className="flex flex-row items-center gap-3 mt-1 pl-6 text-xs text-gray-400">
            <span className="flex items-center gap-1 group-hover:text-gray-500 transition-colors">
              {story.status === "complete" ? (
                <CheckCircle2 className="w-3 h-3 text-green-500" />
              ) : (
                <Clock className="w-3 h-3 text-yellow-500 pr-1 animate-pulse" />
              )}
              {story.status}
            </span>
            <span>{story.entity_count} entities</span>
          </div>
        </button>
      ))}
    </div>
  );
};
