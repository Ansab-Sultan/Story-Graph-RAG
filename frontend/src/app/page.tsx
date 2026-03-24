"use client";
import React, { useEffect, useState } from "react";
import { useAppContext } from "@/context/AppContext";
import { api } from "@/lib/api";
import dynamic from "next/dynamic";
import { ChatArea } from "@/components/chat/ChatArea";
import { Layers } from "lucide-react";

const GraphVisualization = dynamic(
  () => import("@/components/graph/GraphVisualization").then((mod) => mod.GraphVisualization),
  { ssr: false, loading: () => <div className="absolute inset-0 flex items-center justify-center text-gray-500">Loading graph environment...</div> }
);

export default function Home() {
  const { selectedStoryId } = useAppContext();
  const [graphData, setGraphData] = useState<any>(null);

  useEffect(() => {
    if (selectedStoryId) {
      api.getStoryGraph(selectedStoryId).then(setGraphData).catch(console.error);
    } else {
      setGraphData(null);
    }
  }, [selectedStoryId]);

  return (
    <div className="flex flex-col lg:flex-row h-full w-full overflow-hidden bg-[var(--background)]">
      {/* Graph Area / Main Content Area */}
      <div className="flex-1 h-1/2 lg:h-full relative overflow-hidden bg-slate-50 dark:bg-[var(--background)]">
        {!selectedStoryId ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400 gap-4">
            <Layers className="w-16 h-16 opacity-20" />
            <h1 className="text-2xl font-semibold text-[var(--foreground)] tracking-tight">Story Graph RAG</h1>
            <p>Select a story from the library to view its knowledge graph.</p>
          </div>
        ) : (
          <GraphVisualization graphData={graphData} />
        )}
      </div>

      {/* Chat Area Panel */}
      <div className="w-full lg:w-[450px] xl:w-[500px] h-1/2 lg:h-full border-t lg:border-t-0 lg:border-l border-[var(--color-border)] flex flex-col bg-[var(--color-surface)] shadow-2xl z-20">
        <ChatArea />
      </div>
    </div>
  );
}
