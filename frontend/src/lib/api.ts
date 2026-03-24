/**
 * API client to interact with the FastAPI backend.
 * Uses Next.js proxy rewrite `/api/*` to `http://127.0.0.1:8000/api/*`.
 */

export interface Story {
  _id: string;
  title: string;
  filename: string;
  display_name: string;
  status: string;
  entity_count: number;
  relationship_count: number;
  chunk_count: number;
  created_at: string;
}

export interface ChatSummary {
  chat_id: string;
  thread_id: string;
  story_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
  last_user_message: string;
  last_answer_preview: string;
}

export interface TranscriptItem {
  type: "user" | "assistant";
  content: string;
  routing_reason?: string;
  query_type?: string;
  citations?: Array<{
    type: string;
    reference: string;
    excerpt: string;
  }>;
  evidence?: any;
}

export interface GraphData {
  nodes: Array<{ id: string; label: string; group?: string; [key: string]: any }>;
  edges: Array<{ source: string; target: string; label?: string; [key: string]: any }>;
}

export const api = {
  getStories: async (): Promise<Story[]> => {
    const res = await fetch('/api/stories');
    if (!res.ok) throw new Error("Failed to fetch stories");
    return res.json();
  },

  getStoryChats: async (storyId: string): Promise<ChatSummary[]> => {
    const res = await fetch(`/api/stories/${storyId}/chats`);
    if (!res.ok) throw new Error("Failed to fetch chats");
    return res.json();
  },

  getChatMessages: async (storyId: string, chatId: string): Promise<TranscriptItem[]> => {
    const res = await fetch(`/api/stories/${storyId}/chats/${chatId}/messages`);
    if (!res.ok) throw new Error("Failed to fetch messages");
    return res.json();
  },

  sendMessage: async (storyId: string, message: string, chatId?: string) => {
    const res = await fetch(`/api/stories/${storyId}/chats/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, chat_id: chatId })
    });
    if (!res.ok) throw new Error("Failed to send message");
    return res.json();
  },

  getStoryGraph: async (storyId: string): Promise<GraphData> => {
    const res = await fetch(`/api/stories/${storyId}/graph`);
    if (!res.ok) throw new Error("Failed to fetch graph");
    return res.json();
  },

  getStoryChunks: async (storyId: string): Promise<any[]> => {
    const res = await fetch(`/api/stories/${storyId}/chunks`);
    if (!res.ok) throw new Error("Failed to fetch chunks");
    return res.json();
  }
};
