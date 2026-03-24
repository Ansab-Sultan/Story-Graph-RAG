"use client";

import React, { useState } from "react";
import { StorySelector } from "@/components/sidebar/StorySelector";
import { ChatHistory } from "@/components/sidebar/ChatHistory";
import { UploadModal } from "@/components/upload/UploadModal";
import { PlusCircle, Search, Menu } from "lucide-react";

export const AppLayout = ({ children }: { children: React.ReactNode }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  return (
    <div className="flex h-screen bg-[var(--background)] text-[var(--foreground)] overflow-hidden font-sans">
      {/* Sidebar */}
      <aside
        className={`${
          isSidebarOpen ? "w-72" : "w-0"
        } transition-brand flex-shrink-0 flex flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)] sm:relative absolute z-40 h-full overflow-hidden`}
      >
        <div className="p-4 flex items-center justify-between border-b border-[var(--color-border)] shrink-0 h-16">
          <div className="flex items-center gap-2 text-primary font-bold text-lg tracking-tight">
            <Search className="w-5 h-5 text-primary" />
            Story Graph RAG
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <h3 className="text-xs uppercase font-semibold text-gray-500 tracking-wider">Library</h3>
            <StorySelector />
            <button 
              onClick={() => setIsUploadOpen(true)}
              className="mt-2 flex items-center gap-2 text-sm text-[var(--color-secondary)] hover:text-primary transition-colors py-2 px-3 rounded-md hover:bg-[var(--color-surface-hover)] border border-dashed border-[var(--color-border)]"
            >
              <PlusCircle className="w-4 h-4" />
              Upload New Story
            </button>
          </div>

          <div className="flex flex-col gap-2">
            <h3 className="text-xs uppercase font-semibold text-gray-500 tracking-wider">Chats</h3>
            <ChatHistory />
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full min-w-0 bg-[var(--background)] relative">
        <header className="h-16 shrink-0 flex items-center px-4 border-b border-[var(--color-border)] bg-[var(--color-surface)]/80 backdrop-blur-md sticky top-0 z-30">
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-2 -ml-2 rounded-md hover:bg-[var(--color-surface-hover)] text-gray-500"
          >
            <Menu className="w-5 h-5" />
          </button>
        </header>

        <div className="flex-1 overflow-hidden relative">
          {children}
        </div>
      </main>

      {isUploadOpen && (
        <UploadModal onClose={() => setIsUploadOpen(false)} />
      )}
    </div>
  );
};
