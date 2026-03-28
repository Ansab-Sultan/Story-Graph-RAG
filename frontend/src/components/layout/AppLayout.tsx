"use client";

import React, { useState } from "react";
import { StorySelector } from "@/components/sidebar/StorySelector";
import { ChatHistory } from "@/components/sidebar/ChatHistory";
import { UploadModal } from "@/components/upload/UploadModal";
import { PlusCircle, Search, Menu } from "lucide-react";
import { BackgroundTasks } from "@/components/layout/BackgroundTasks";

export const AppLayout = ({ children }: { children: React.ReactNode }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  return (
    <div className="flex h-screen bg-[var(--background)] text-[var(--foreground)] overflow-hidden font-sans transition-premium">
      {/* Sidebar */}
      <aside
        className={`${
          isSidebarOpen ? "w-80" : "w-0"
        } transition-premium flex-shrink-0 flex flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)] sm:relative absolute z-40 h-full overflow-hidden`}
      >
        <div className="px-6 flex items-center justify-between border-b border-[var(--color-border)] shrink-0 h-16">
          <div className="flex items-center gap-3 group cursor-default">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-secondary)] flex items-center justify-center shadow-lg shadow-[var(--color-primary)]/20 group-hover:scale-110 transition-premium">
              <Search className="w-5 h-5 text-white" />
            </div>
            <div className="flex flex-row items-baseline gap-1.5 min-w-max">
              <span className="text-lg font-black tracking-tighter leading-none text-[var(--text-primary)]">STORY</span>
              <span className="text-lg font-black tracking-tighter leading-none bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-secondary)] bg-clip-text text-transparent">GRAPH</span>
            </div>
          </div>
          
          <button
            onClick={() => setIsSidebarOpen(false)}
            className="p-2 -mr-2 rounded-lg hover:bg-[var(--surface-hover)] transition-premium hover:rotate-90 text-[var(--color-muted)] cursor-pointer active:scale-90"
            title="Collapse Workspace"
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 pb-0 flex flex-col no-scrollbar custom-scrollbar">
          <div className="flex flex-col gap-4 mb-10">
            <div className="flex items-center justify-between px-1">
              <h3 className="text-[10px] uppercase font-bold text-[var(--color-muted)] tracking-[0.2em]">Library</h3>
              <div className="h-px flex-1 bg-[var(--color-border)] ml-4 opacity-50" />
            </div>
            <StorySelector />
            <button 
              onClick={() => setIsUploadOpen(true)}
              className="mt-2 relative overflow-hidden flex items-center justify-center gap-2.5 text-[13px] font-bold text-white transition-premium py-3.5 px-4 rounded-xl bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] shadow-lg shadow-[var(--color-primary)]/20 border border-white/10 cursor-pointer group hover:-translate-y-0.5 active:scale-[0.98]"
            >
              <div className="absolute inset-0 bg-gradient-to-tr from-white/0 via-white/10 to-white/0 translate-x-[-200%] group-hover:translate-x-[200%] transition-transform duration-1000" />
              <PlusCircle className="w-4 h-4 transition-premium group-hover:rotate-90" />
              Upload New Story
            </button>
          </div>

          <div className="flex flex-col gap-4 mb-10">
            <div className="flex items-center justify-between px-1">
              <h3 className="text-[10px] uppercase font-bold text-[var(--color-muted)] tracking-[0.2em]">Recent Analysis</h3>
              <div className="h-px flex-1 bg-[var(--color-border)] ml-4 opacity-50" />
            </div>
            <ChatHistory />
          </div>

          <BackgroundTasks />
        </div>

        {/* Sidebar Footer: Theme Toggle & User */}
        <div className="p-6 border-t border-[var(--color-border)] flex flex-col items-center gap-6 bg-[var(--color-surface)]">
          
          <div className="flex items-center gap-3 w-full p-2 rounded-xl hover:bg-[var(--color-surface-hover)] transition-premium cursor-pointer group">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-secondary)] flex items-center justify-center text-white font-black text-xs shadow-lg">
              AS
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-black text-[var(--text-primary)] truncate tracking-tight group-hover:text-[var(--color-primary)] transition-premium">Ansab Sultan</span>
              <span className="text-[10px] text-[var(--color-muted)] font-bold truncate tracking-wider uppercase">Lead Architect</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full min-w-0 bg-[var(--background)] relative">
        {/* Floating Sidebar Toggle (Only when closed) */}
        {!isSidebarOpen && (
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="absolute top-4 left-4 z-50 p-2.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]/80 backdrop-blur-md shadow-xl text-[var(--color-muted)] hover:text-[var(--color-primary)] hover:scale-110 active:scale-90 transition-premium cursor-pointer group animate-in slide-in-from-left-4 duration-300"
            title="Expand Workspace"
          >
            <Menu className="w-5 h-5 transition-premium group-hover:rotate-180" />
          </button>
        )}

        <header className="h-16 shrink-0 flex items-center px-4 border-b border-[var(--color-border)] bg-[var(--color-surface)]/80 backdrop-blur-md sticky top-0 z-30">
          {/* Header Content can go here in the future if needed */}
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
