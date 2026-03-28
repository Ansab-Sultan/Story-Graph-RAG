"use client";
import React, { useEffect, useState } from "react";
import { useAppContext } from "@/context/AppContext";
import { api } from "@/lib/api";
import dynamic from "next/dynamic";
import { ChatArea } from "@/components/chat/ChatArea";
import { Network, Sparkles, MessageSquare, Info } from "lucide-react";

const GraphVisualization = dynamic(
  () => import("@/components/graph/GraphVisualization").then((mod) => mod.GraphVisualization),
  { 
    ssr: false, 
    loading: () => (
      <div className="absolute inset-0 flex flex-col items-center justify-center bg-[var(--background)] z-50 gap-4">
        <div className="w-12 h-12 border-4 border-[var(--color-primary)]/20 border-t-[var(--color-primary)] rounded-full animate-spin" />
        <p className="text-sm font-medium text-[var(--color-muted)] animate-pulse">Initializing Neural Graph...</p>
      </div>
    ) 
  }
);

export default function Home() {
  const { selectedStoryId, stories } = useAppContext();
  const [graphData, setGraphData] = useState<any>(null);
  
  const selectedStory = stories.find((story) => story.story_id === selectedStoryId);

  useEffect(() => {
    if (selectedStoryId) {
      api.getStoryGraph(selectedStoryId).then(setGraphData).catch(console.error);
    } else {
      setGraphData(null);
    }
  }, [selectedStoryId]);

  return (
    <div className="flex flex-col lg:flex-row h-full w-full overflow-hidden bg-[var(--background)] transition-premium">
      {/* Main Viewport: Graph Area */}
      <div className="flex-1 h-full relative overflow-hidden bg-[var(--background)] neural-grid">
        {!selectedStoryId ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-8 text-center animate-in fade-in slide-in-from-bottom-8 duration-1000">
            {/* Animated Neural Pulse Background */}
            <div className="absolute inset-0 flex items-center justify-center overflow-hidden pointer-events-none">
              <div className="absolute w-[400px] h-[400px] rounded-full border border-[var(--color-primary)]/10 animate-[neural-pulse_4s_infinite]" />
              <div className="absolute w-[300px] h-[300px] rounded-full border border-[var(--color-secondary)]/10 animate-[neural-pulse_6s_infinite]" />
              <div className="absolute w-[200px] h-[200px] rounded-full border border-[var(--color-accent)]/10 animate-[neural-pulse_8s_infinite]" />
            </div>

            <div className="relative mb-12 group">
              {/* Complex Orbital System */}
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-[180px] h-[180px] rounded-full border border-[var(--text-primary)]/[0.03] animate-[spin_30s_linear_infinite]" />
                <div className="w-[220px] h-[220px] rounded-full border border-dashed border-[var(--text-primary)]/[0.02] animate-[spin_60s_linear_infinite_reverse]" />
                
                {/* Orbiting Data Particles */}
                <div className="absolute w-1 h-1 bg-[var(--color-primary)] rounded-full blur-[1px] animate-[orbit_8s_linear_infinite]" />
                <div className="absolute w-1 h-1 bg-[var(--color-secondary)] rounded-full blur-[1px] animate-[orbit_12s_linear_infinite_reverse]" />
              </div>

              {/* Corner Brackets */}
              <div className="absolute -inset-6 pointer-events-none">
                <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-[var(--color-primary)]/30 rounded-tl-lg animate-corner-pulse" />
                <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-[var(--color-primary)]/30 rounded-tr-lg animate-corner-pulse [animation-delay:0.5s]" />
                <div className="absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 border-[var(--color-primary)]/30 rounded-bl-lg animate-corner-pulse [animation-delay:1s]" />
                <div className="absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2 border-[var(--color-primary)]/30 rounded-br-lg animate-corner-pulse [animation-delay:1.5s]" />
              </div>

              {/* High-End Glass Core */}
              <div className="relative w-40 h-40 rounded-[3rem] p-[1px] bg-gradient-to-br from-[var(--text-primary)]/20 to-transparent shadow-2xl group-hover:scale-105 transition-premium cursor-default active:scale-95">
                <div className="absolute inset-0 rounded-[3rem] bg-gradient-to-br from-[var(--color-primary)]/20 via-transparent to-[var(--color-secondary)]/20 blur-xl opacity-50 group-hover:opacity-100 transition-premium" />
                
                <div className="relative w-full h-full rounded-[3rem] bg-[var(--bg-secondary)] backdrop-blur-2xl flex flex-col items-center justify-center overflow-hidden border border-[var(--text-primary)]/5">
                  {/* Light Sweep Effect */}
                  <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-transparent via-[var(--text-primary)]/[0.05] to-transparent -translate-x-full -translate-y-full animate-light-sweep" />
                  
                  {/* Neural Glow Core */}
                  <div className="absolute w-20 h-20 bg-[var(--color-primary)] blur-[40px] opacity-20 animate-pulse" />
                  
                  <Network className="w-20 h-20 text-[var(--color-primary)] drop-shadow-[0_0_20px_var(--glow-primary)] z-10 animate-iridescent" />
                  
                  {/* Active Status Badge */}
                  <div className="absolute bottom-4 flex items-center gap-1.5 px-3 py-1 rounded-full bg-[var(--text-primary)]/5 border border-[var(--text-primary)]/10 z-20">
                    <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-pulse shadow-[0_0_8px_var(--color-primary)]" />
                    <span className="text-[8px] font-black uppercase tracking-[0.2em] text-[var(--text-primary)]/40">Neural Link</span>
                  </div>
                </div>
              </div>
            </div>
            
            <h1 className="text-5xl font-black tracking-tighter mb-4 text-[var(--text-primary)] drop-shadow-sm">
              Unfold Nuclear <span className="text-transparent bg-clip-text bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-secondary)]">Narratives</span>
            </h1>
            <p className="max-w-md text-[var(--color-muted)] leading-relaxed text-lg mb-10 font-medium">
              Select a story from your library to visualize its knowledge graph and begin deep-narrative analysis.
            </p>
            
            <div className="flex items-center gap-10">
               <div className="flex flex-col items-center gap-3 transition-premium hover:scale-110 active:scale-95 group cursor-default">
                  <div className="w-14 h-14 rounded-2xl bg-[var(--bg-secondary)] border border-[var(--border-primary)] flex items-center justify-center shadow-xl group-hover:border-[var(--accent-secondary)] transition-premium glass-panel">
                    <Sparkles className="w-6 h-6 text-[var(--color-accent)] drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]" />
                  </div>
                  <span className="text-[10px] uppercase font-black text-[var(--color-muted)] tracking-[0.2em]">AI Insights</span>
               </div>
               <div className="flex flex-col items-center gap-3 transition-premium hover:scale-110 active:scale-95 group cursor-default">
                  <div className="w-14 h-14 rounded-2xl bg-[var(--bg-secondary)] border border-[var(--border-primary)] flex items-center justify-center shadow-xl group-hover:border-[var(--color-primary)] transition-premium glass-panel">
                    <MessageSquare className="w-6 h-6 text-[var(--color-primary)] drop-shadow-[0_0_8px_rgba(0,82,255,0.5)]" />
                  </div>
                  <span className="text-[10px] uppercase font-black text-[var(--color-muted)] tracking-[0.2em]">Graph Chat</span>
               </div>
            </div>
          </div>
        ) : (
          <>
            {/* Context Header HUD */}
            <div className="absolute top-8 left-8 z-20 flex items-center gap-4 glass-panel px-5 py-3 rounded-2xl shadow-2xl border border-[var(--color-border)] animate-in fade-in slide-in-from-top-4 duration-500">
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-[var(--color-success)] animate-pulse shadow-[0_0_10px_var(--color-success)]" />
                <span className="text-[10px] uppercase font-black text-[var(--color-muted)] tracking-widest">Active Insight</span>
              </div>
              <div className="w-px h-4 bg-[var(--color-border)]" />
              <span className="text-sm font-bold text-[var(--text-primary)] tracking-tight truncate max-w-[250px]">{selectedStory?.display_name || selectedStory?.title}</span>
              <Info className="w-4 h-4 text-[var(--color-accent)] cursor-help hover:scale-110 transition-premium" />
            </div>

            <div className="w-full h-full bg-[var(--background)]">
              <GraphVisualization graphData={graphData} />
            </div>
          </>
        )}
      </div>

      {/* Action Drawer: Chat & Details */}
      <div className={clsx(
        "w-full lg:w-[450px] xl:w-[500px] h-1/2 lg:h-full transition-premium z-20 flex flex-col glass-panel border-t lg:border-t-0 lg:border-l border-[var(--color-border)]",
        !selectedStoryId && "opacity-50 pointer-events-none grayscale-[0.5]"
      )}>
        <ChatArea />
      </div>
    </div>
  );
}

function clsx(...classes: any[]) {
  return classes.filter(Boolean).join(" ");
}
