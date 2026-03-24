"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { Story, ChatSummary, api } from "@/lib/api";

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
};

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider = ({ children }: { children: ReactNode }) => {
  const [stories, setStories] = useState<Story[]>([]);
  const [selectedStoryId, setSelectedStoryId] = useState<string | null>(null);
  
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);

  const [highlightedNodes, setHighlightedNodes] = useState<string[]>([]);

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
        setHighlightedNodes
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
