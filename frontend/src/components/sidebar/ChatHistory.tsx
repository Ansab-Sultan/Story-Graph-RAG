"use client";
import React from "react";
import { useAppContext } from "@/context/AppContext";
import { MessageSquare, Plus } from "lucide-react";
import clsx from "clsx";

export const ChatHistory = () => {
  const { chats, selectedStoryId, selectedChatId, setSelectedChatId } = useAppContext();

  if (!selectedStoryId) {
    return <div className="text-sm text-gray-500 italic px-2">Select a story to see chats.</div>;
  }

  return (
    <div className="flex flex-col gap-1">
      {chats.map((chat) => (
        <button
          key={chat.chat_id}
          onClick={() => setSelectedChatId(chat.chat_id)}
          className={clsx(
            "flex flex-col text-left px-3 py-2 rounded-md transition-all duration-200 text-sm w-full group cursor-pointer",
            selectedChatId === chat.chat_id
              ? "bg-slate-100 dark:bg-slate-800 text-[var(--foreground)] font-medium border border-slate-200 dark:border-slate-700 shadow-sm"
              : "hover:bg-[var(--color-surface-hover)] hover:shadow-[0_2px_8px_-2px_rgba(0,0,0,0.05)] hover:-translate-y-0.5 border border-transparent text-gray-600 dark:text-gray-400"
          )}
        >
          <div className="flex flex-row items-center gap-2">
            <MessageSquare className="w-4 h-4 shrink-0" />
            <span className="truncate">{chat.title || chat.last_user_message || "New Chat"}</span>
          </div>
          {chat.last_answer_preview && (
            <div className="mt-1 pl-6 text-xs text-gray-400 truncate w-full">
              {chat.last_answer_preview}
            </div>
          )}
        </button>
      ))}
      <button 
        onClick={() => setSelectedChatId(null)}
        className="mt-2 flex items-center gap-2 text-sm text-[var(--color-primary)] bg-transparent hover:bg-[var(--color-surface-hover)] py-2 px-3 rounded-md transition-all duration-200 hover:-translate-y-0.5 hover:shadow-sm border border-transparent cursor-pointer"
      >
        <Plus className="w-4 h-4" />
        New Chat
      </button>
    </div>
  );
};
