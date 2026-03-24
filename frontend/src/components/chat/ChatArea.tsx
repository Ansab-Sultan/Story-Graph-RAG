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
      <div className="flex-1 flex flex-col items-center justify-center text-gray-500 p-8 text-center bg-[var(--background)]">
        <Bot className="w-12 h-12 mb-4 opacity-20" />
        <h3 className="text-lg font-medium text-[var(--foreground)]">No Story Selected</h3>
        <p className="mt-2 text-sm">Select a story from the library to start analyzing and chatting.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[var(--background)]">
      {/* Header */}
      <div className="p-4 border-b border-[var(--color-border)] bg-[var(--color-surface)] shrink-0 flex items-center justify-between shadow-sm">
        <h2 className="font-semibold text-[var(--foreground)] tracking-tight">Graph Agent</h2>
        {selectedChatId && (
          <span className="text-xs bg-slate-100 dark:bg-slate-800 text-gray-500 px-2 py-1 rounded-md font-mono border border-[var(--color-border)]">
            {selectedChatId.split("-")[0]}
          </span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-400">
            <Bot className="w-10 h-10 mb-3 opacity-30" />
            <p className="text-sm">Ask me about characters, events, or relationships in the story.</p>
            <div className="mt-6 flex flex-col gap-2 w-full max-w-xs">
              <button onClick={() => setInput("Who are the main characters?")} className="text-xs text-left px-3 py-2 bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] border border-[var(--color-border)] rounded-md transition-colors">"Who are the main characters?"</button>
              <button onClick={() => setInput("What events led to the climax?")} className="text-xs text-left px-3 py-2 bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] border border-[var(--color-border)] rounded-md transition-colors">"What events led to the climax?"</button>
              <button onClick={() => setInput("Describe the relationships of the protagonist.")} className="text-xs text-left px-3 py-2 bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] border border-[var(--color-border)] rounded-md transition-colors">"Describe the relationships of the protagonist."</button>
            </div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} className={clsx("flex gap-3", msg.type === "user" ? "justify-end" : "justify-start")}>
              {msg.type === "assistant" && (
                <div className="w-8 h-8 rounded-full bg-[var(--color-primary)] text-white flex items-center justify-center shrink-0 shadow-sm mt-1">
                  <Bot className="w-5 h-5" />
                </div>
              )}
              
              <div 
                className={clsx(
                  "max-w-[85%] rounded-2xl p-4 shadow-sm",
                  msg.type === "user" 
                    ? "bg-[var(--color-primary)] text-white rounded-br-none" 
                    : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--foreground)] rounded-bl-none"
                )}
              >
                {msg.type === "user" ? (
                  <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                ) : (
                  <div className="flex flex-col">
                    <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                    
                    {(msg.citations || msg.routing_reason) && (
                      <EvidenceDrawer 
                        citations={msg.citations || []} 
                        routingReason={msg.routing_reason} 
                        queryType={msg.query_type}
                      />
                    )}
                  </div>
                )}
              </div>

              {msg.type === "user" && (
                <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-300 flex items-center justify-center shrink-0 mt-1">
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
            className="absolute right-2 p-2 bg-[var(--color-primary)] text-white rounded-full hover:bg-[var(--color-primary-hover)] disabled:bg-gray-300 dark:disabled:bg-slate-800 disabled:text-gray-400 transition-colors shadow-sm"
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
