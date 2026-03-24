"use client";
import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BookOpen, Network, Database } from "lucide-react";

export const EvidenceDrawer = ({ citations, routingReason, queryType }: { citations: any[]; routingReason?: string; queryType?: string }) => {
  
  const renderReason = () => {
    if (!routingReason) return null;
    let Icon = Database;
    if (queryType === "graph") Icon = Network;
    if (queryType === "hybrid") Icon = BookOpen;

    return (
      <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-900/50 rounded-lg flex items-start gap-3 text-sm">
        <Icon className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-blue-700 dark:text-blue-400 capitalize">{queryType} Retrieval: </span>
          <span className="text-blue-600 dark:text-blue-300">{routingReason}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-4 mt-6 pt-6 border-t border-[var(--color-border)]">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-500">Evidence & Citations</h3>
      {renderReason()}

      {citations?.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {citations.map((c, i) => (
            <div key={i} className="bg-[var(--color-surface-hover)] p-4 rounded-xl border border-[var(--color-border)] text-sm shadow-sm space-y-2">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 bg-[var(--color-primary)] text-white text-xs font-bold rounded-md uppercase">
                  {c.type}
                </span>
                <span className="font-mono text-xs text-gray-500">{c.reference}</span>
              </div>
              <div className="prose prose-sm dark:prose-invert max-w-none text-gray-600 dark:text-gray-300">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {c.excerpt}
                </ReactMarkdown>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-sm text-gray-400 italic">No direct citations returned for this answer.</div>
      )}
    </div>
  );
};
