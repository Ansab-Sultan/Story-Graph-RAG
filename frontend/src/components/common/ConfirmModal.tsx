"use client";

import React from "react";
import { AlertCircle, X } from "lucide-react";
import clsx from "clsx";

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  isDestructive?: boolean;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  isDestructive = false,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 sm:p-6 animate-in fade-in duration-300">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" 
        onClick={onCancel}
      />

      {/* Modal Container */}
      <div className={clsx(
        "relative w-full max-w-md glass-panel rounded-[2rem] overflow-hidden animate-in zoom-in-95 slide-in-from-bottom-4 duration-300 border border-[var(--color-border)]",
        "bg-[var(--color-surface)]"
      )}>
        {/* Header/Close */}
        <div className="absolute top-4 right-4">
          <button
            onClick={onCancel}
            className="p-2 rounded-full text-[var(--color-muted)] hover:text-[var(--foreground)] hover:bg-[var(--surface-hover)] transition-premium cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-8 pt-10 flex flex-col items-center text-center">
          {/* Icon Section */}
          <div className={clsx(
            "w-20 h-20 rounded-[2rem] flex items-center justify-center mb-6 relative group transition-premium",
            isDestructive 
              ? "bg-[var(--color-error)]/10 text-[var(--color-error)] shadow-[0_0_40px_-10px_rgba(239,68,68,0.2)]" 
              : "bg-[var(--color-primary)]/10 text-[var(--color-primary)] shadow-[0_0_40px_-10px_var(--accent-glow)]"
          )}>
            <div className={clsx(
              "absolute inset-0 rounded-[2rem] blur-xl opacity-20 group-hover:opacity-40 transition-premium",
              isDestructive ? "bg-[var(--color-error)]" : "bg-[var(--color-primary)]"
            )} />
            <AlertCircle className="w-10 h-10 relative z-10" />
          </div>

          {/* Content */}
          <h3 className="text-2xl font-black tracking-tight mb-3 text-[var(--text-primary)]">
            {title}
          </h3>
          <p className="text-[var(--color-muted)] text-sm leading-relaxed mb-8 max-w-[280px] font-medium">
            {message}
          </p>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 w-full">
            <button
              onClick={onCancel}
              className="flex-1 px-6 py-4 rounded-2xl bg-[var(--surface-secondary)] hover:bg-[var(--surface-hover)] text-[var(--text-primary)] font-bold transition-premium cursor-pointer active:scale-95 border border-[var(--color-border)]"
            >
              {cancelLabel}
            </button>
            <button
              onClick={onConfirm}
              className={clsx(
                "flex-1 px-6 py-4 rounded-2xl font-black transition-premium shadow-xl cursor-pointer active:scale-95 text-white",
                isDestructive 
                  ? "bg-[var(--color-error)] hover:bg-[var(--color-error)]/90 shadow-[var(--color-error)]/20" 
                  : "bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] shadow-[var(--color-primary)]/20"
              )}
            >
              {confirmLabel}
            </button>
          </div>
        </div>

        {/* Decorative Bottom Glow */}
        <div className={clsx(
          "h-1 w-full opacity-30",
          isDestructive ? "bg-gradient-to-r from-transparent via-[var(--color-error)] to-transparent" : "bg-gradient-to-r from-transparent via-[var(--color-primary)] to-transparent"
        )} />
      </div>
    </div>
  );
};
