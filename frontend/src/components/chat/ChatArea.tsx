"use client";
import React, { useState, useEffect, useRef } from "react";
import { useAppContext } from "@/context/AppContext";
import { api, TranscriptItem } from "@/lib/api";
import { Send, User, Bot, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { EvidenceDrawer } from "@/components/evidence/EvidenceDrawer";
import clsx from "clsx";

export const ChatArea = () => {
  const { selectedStoryId, selectedChatId, setSelectedChatId, refreshChats, setHighlightedNodes } = useAppContext();
  const [messages, setMessages] = useState<TranscriptItem[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selectedStoryId && selectedChatId) {
      api.getChatMessages(selectedStoryId, selectedChatId)
        .then(data => {
          setMessages(data);
          // Highlight nodes from the last assistant message
          const lastMsg = data[data.length - 1];
          if (lastMsg && lastMsg.citations) {
            const hNodes = lastMsg.citations
              .filter(c => c.type === "graph_node")
              .map(c => c.reference);
            setHighlightedNodes(hNodes);
          } else {
            setHighlightedNodes([]);
          }
        })
        .catch(console.error);
    } else {
      setMessages([]);
      setHighlightedNodes([]);
    }
  }, [selectedStoryId, selectedChatId, setHighlightedNodes]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !selectedStoryId || isSending) return;

    const userText = input.trim();
    setInput("");
    
    // Optimistic UI updates
    const tempUserMsg: TranscriptItem = { type: "user", content: userText };
    setMessages((prev) => [...prev, tempUserMsg]);
    setIsSending(true);
    setHighlightedNodes([]); // clear highlights while thinking

    try {
      const res = await api.sendMessage(selectedStoryId, userText, selectedChatId || undefined);
      
      if (!selectedChatId) {
        setSelectedChatId(res.chat_id);
      }
      refreshChats();

      setMessages((prev) => [
        ...prev,
        {
          type: "assistant",
          content: res.answer,
          routing_reason: res.routing_reason,
          query_type: res.query_type,
          citations: res.citations,
          evidence: res.evidence,
        }
      ]);
      
      const hNodes = (res.citations || [])
        .filter((c: any) => c.type === "graph_node")
        .map((c: any) => c.reference);
      setHighlightedNodes(hNodes);
      
    } catch (err) {
      console.error(err);
      setMessages((prev) => [...prev, { type: "assistant", content: "Sorry, an error occurred while processing your request." }]);
    } finally {
      setIsSending(false);
    }
  };

  if (!selectedStoryId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-12 text-center bg-[var(--background)] animate-in fade-in duration-700">
        <div className="relative mb-6">
          <div className="absolute inset-0 bg-[var(--color-primary)] blur-[60px] opacity-10 animate-pulse" />
          <div className="relative w-20 h-20 rounded-2xl bg-[var(--color-surface)] border border-white/5 flex items-center justify-center shadow-xl">
            <Bot className="w-10 h-10 text-[var(--color-muted)] opacity-40 group-hover:opacity-100 transition-premium" />
          </div>
        </div>
        <h3 className="text-xl font-black text-[var(--text-primary)] tracking-tight mb-2">Neural Link Awaiting</h3>
        <p className="max-w-[280px] text-sm text-[var(--color-muted)] leading-relaxed font-medium">
          Select a story from your library to initialize the graph agent and begin deep-narrative interrogation.
        </p>
        
        <div className="mt-8 flex flex-col gap-3 w-full max-w-[240px]">
          <div className="h-px w-full bg-gradient-to-r from-transparent via-[var(--color-border)] to-transparent" />
          <div className="flex items-center justify-center gap-2 text-[10px] uppercase font-black text-[var(--color-muted)] tracking-widest">
            <div className="w-1 h-1 rounded-full bg-[var(--color-muted)] animate-pulse" />
            System Idle
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[var(--background)]">
      {/* Header */}
      <div className="px-6 border-b border-[var(--color-border)] bg-[var(--color-surface)] shrink-0 flex items-center justify-between shadow-sm h-16">
        <h2 className="font-semibold text-[var(--text-primary)] tracking-tight">Graph Agent</h2>
        {selectedChatId && (
          <span className="text-[10px] bg-[var(--surface-secondary)] text-[var(--color-muted)] px-2 py-1 rounded-md font-black uppercase tracking-widest border border-[var(--color-border)]">
            {selectedChatId.split("-")[0]}
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {!Array.isArray(messages) || messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-400">
            <Bot className="w-10 h-10 mb-3 opacity-30" />
            <p className="text-sm">Ask me about characters, events, or relationships in the story.</p>
            <div className="mt-6 flex flex-col gap-2 w-full max-w-xs">
              <button onClick={() => setInput("Who are the main characters?")} className="text-xs text-left px-3 py-2 bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] border border-[var(--color-border)] rounded-md transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md cursor-pointer">"Who are the main characters?"</button>
              <button onClick={() => setInput("What events led to the climax?")} className="text-xs text-left px-3 py-2 bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] border border-[var(--color-border)] rounded-md transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md cursor-pointer">"What events led to the climax?"</button>
              <button onClick={() => setInput("Describe the relationships of the protagonist.")} className="text-xs text-left px-3 py-2 bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] border border-[var(--color-border)] rounded-md transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md cursor-pointer">"Describe the relationships of the protagonist."</button>
            </div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div
              key={i}
              className={clsx(
                "flex mb-8 animate-in slide-in-from-bottom-2 duration-500 transition-premium",
                msg.type === "user" ? "justify-end" : "justify-start gap-4"
              )}
            >
              {msg.type === "assistant" && (
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-secondary)] text-white flex items-center justify-center shrink-0 shadow-lg mt-1 accent-glow">
                  <Bot className="w-5 h-5" />
                </div>
              )}
              
              <div
                className={clsx(
                  "max-w-[85%] px-6 py-4 rounded-2xl transition-premium relative",
                  msg.type === "user"
                    ? "bg-[var(--color-primary)] text-white border-[var(--color-primary)]/20 rounded-tr-none shadow-blue-500/10"
                    : "bg-[var(--surface-secondary)] border border-[var(--color-border)] text-[var(--text-primary)] rounded-tl-none glass-panel"
                )}
              >
                <div className={clsx(
                  "prose prose-sm max-w-none prose-p:leading-relaxed",
                  msg.type === "user" ? "text-white prose-invert" : "text-[var(--text-primary)] dark:prose-invert"
                )}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content}
                  </ReactMarkdown>
                </div>

                {msg.type === "assistant" && (msg.citations || msg.routing_reason) && (
                  <div className="mt-4 pt-4 border-t border-[var(--color-border)]/50">
                    <EvidenceDrawer 
                      citations={msg.citations || []} 
                      routingReason={msg.routing_reason} 
                      queryType={msg.query_type}
                    />
                  </div>
                )}
              </div>

              {msg.type === "user" && (
                <div className="w-9 h-9 rounded-xl bg-[var(--surface-secondary)] border border-[var(--color-border)] text-[var(--text-secondary)] flex items-center justify-center shrink-0 shadow-sm mt-1 ml-4 glass-panel">
                  <User className="w-5 h-5" />
                </div>
              )}
            </div>
          ))
        )}
        
        {isSending && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-full bg-[var(--color-primary)] text-white flex items-center justify-center shrink-0 shadow-sm mt-1">
              <Bot className="w-5 h-5" />
            </div>
            <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl rounded-bl-none p-4 flex items-center gap-2 shadow-sm">
              <Loader2 className="w-4 h-4 text-[var(--color-primary)] animate-spin" />
              <span className="text-sm text-gray-500 font-medium">Agent is thinking and searching...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} className="h-2" />
      </div>

      {/* Input */}
      <div className="p-4 bg-[var(--color-surface)] border-t border-[var(--color-border)] shrink-0">
        <form onSubmit={handleSend} className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isSending}
            placeholder="Interrogate findings, ask about relationships..."
            className="w-full bg-[var(--background)] border border-[var(--color-border)] text-[var(--foreground)] text-sm rounded-full pl-5 pr-14 py-3.5 focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:border-transparent transition-all shadow-sm placeholder:text-gray-400"
          />
          <button
            type="submit"
            disabled={!input.trim() || isSending}
            className="absolute right-2 p-2 bg-[var(--color-primary)] text-white rounded-full hover:bg-[var(--color-primary-hover)] disabled:bg-gray-300 dark:disabled:bg-slate-800 disabled:text-gray-400 transition-all duration-200 hover:scale-110 active:scale-95 shadow-sm cursor-pointer disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
        <div className="text-center mt-2">
          <span className="text-[10px] text-gray-400 uppercase tracking-widest font-semibold">Story Graph RAG</span>
        </div>
      </div>
    </div>
  );
};
