"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode, useRef } from "react";
import { Story, ChatSummary, api, IngestionJob, IngestionProgress } from "@/lib/api";

type AppContextType = {
  stories: Story[];
  selectedStoryId: string | null;
  setSelectedStoryId: (id: string | null) => void;
  chats: ChatSummary[];
  selectedChatId: string | null;
  setSelectedChatId: (id: string | null) => void;
  refreshStories: () => Promise<void>;
  refreshChats: () => Promise<void>;
  highlightedNodes: string[];
  setHighlightedNodes: (nodes: string[]) => void;
  activeJobs: Record<string, IngestionJob>;
  startIngestion: (storyId: string, filename: string) => void;
  removeJob: (storyId: string) => void;
  deleteStory: (storyId: string) => Promise<void>;
};

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider = ({ children }: { children: ReactNode }) => {
  const [stories, setStories] = useState<Story[]>([]);
  const [selectedStoryId, setSelectedStoryId] = useState<string | null>(null);
  
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);

  const [highlightedNodes, setHighlightedNodes] = useState<string[]>([]);
  const [activeJobs, setActiveJobs] = useState<Record<string, IngestionJob>>({});
  const eventSourcesRef = useRef<Record<string, EventSource>>({});

  const connectToIngestionStream = (
    storyId: string,
    filename: string,
    initialStatus: IngestionJob["status"] = "queued"
  ) => {
    if (eventSourcesRef.current[storyId]) {
      return;
    }

    setActiveJobs(prev => ({
      ...prev,
      [storyId]: {
        story_id: storyId,
        filename,
        status: prev[storyId]?.status ?? initialStatus,
        progress: prev[storyId]?.progress ?? [],
        error: prev[storyId]?.error,
      }
    }));

    const eventSource = new EventSource(`/api/stories/${storyId}/stream`);
    eventSourcesRef.current[storyId] = eventSource;

    eventSource.addEventListener("progress", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data) as IngestionProgress;
        setActiveJobs(prev => {
          const job = prev[storyId];
          if (!job) return prev;

          const nextProgress = [...job.progress, data];
          return {
            ...prev,
            [storyId]: {
              ...job,
              status: (data.status as IngestionJob["status"] | undefined) ?? job.status,
              progress: nextProgress,
              error: data.status === "error" ? job.error : undefined,
            }
          };
        });
      } catch (err) {
        console.error("Error parsing SSE data", err);
      }
    });

    const handleCompletion = (status: 'complete' | 'error', data?: any) => {
      setActiveJobs(prev => {
        const job = prev[storyId];
        if (!job) return prev;
        return {
          ...prev,
          [storyId]: {
            ...job,
            status,
            error: data?.error
          }
        };
      });
      eventSource.close();
      delete eventSourcesRef.current[storyId];
      refreshStories();

      // If it's the first story or no story is selected, maybe select it?
      // For now, just refresh the list.
    };

    eventSource.addEventListener('complete', () => {
      handleCompletion('complete');
    });

    eventSource.addEventListener('job_error', (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        handleCompletion('error', data);
      } catch {
        handleCompletion('error', { error: "Connection lost" });
      }
    });

    eventSource.onerror = () => {
      console.warn(`Ingestion stream interrupted for ${storyId}`);
    };
  };

  const startIngestion = (storyId: string, filename: string) => {
    connectToIngestionStream(storyId, filename, "queued");
  };

  const removeJob = (storyId: string) => {
    const stream = eventSourcesRef.current[storyId];
    if (stream) {
      stream.close();
      delete eventSourcesRef.current[storyId];
    }
    setActiveJobs(prev => {
      const next = { ...prev };
      delete next[storyId];
      return next;
    });
  };

  const deleteStory = async (storyId: string) => {
    try {
      await api.deleteStory(storyId);
      setStories(prev => prev.filter(s => s.story_id !== storyId));
      if (selectedStoryId === storyId) {
        setSelectedStoryId(null);
      }
    } catch (error) {
      console.error("Failed to delete story:", error);
      throw error;
    }
  };



  const refreshStories = async () => {
    try {
      const data = await api.getStories();
      setStories(data);
    } catch (error) {
      console.error("Failed to load stories:", error);
    }
  };

  const refreshChats = async () => {
    if (!selectedStoryId) {
      setChats([]);
      return;
    }
    try {
      const data = await api.getStoryChats(selectedStoryId);
      setChats(data);
    } catch (error) {
      console.error("Failed to load chats:", error);
    }
  };

  useEffect(() => {
    refreshStories();
  }, []);

  useEffect(() => {
    for (const story of stories) {
      if ((story.status === "queued" || story.status === "running") && !eventSourcesRef.current[story.story_id]) {
        connectToIngestionStream(story.story_id, story.display_name || story.filename, story.status);
      }
    }
  }, [stories]);

  useEffect(() => {
    return () => {
      Object.values(eventSourcesRef.current).forEach((source) => source.close());
      eventSourcesRef.current = {};
    };
  }, []);

  useEffect(() => {
    refreshChats();
    setSelectedChatId(null);
    setHighlightedNodes([]);
  }, [selectedStoryId]);

  return (
    <AppContext.Provider
      value={{
        stories,
        selectedStoryId,
        setSelectedStoryId,
        chats,
        selectedChatId,
        setSelectedChatId,
        refreshStories,
        refreshChats,
        highlightedNodes,
        setHighlightedNodes,
        activeJobs,
        startIngestion,
        removeJob,
        deleteStory,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error("useAppContext must be used within an AppProvider");
  }
  return context;
};
