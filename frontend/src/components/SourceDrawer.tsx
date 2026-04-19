"use client";

import { useEffect, useRef } from "react";
import type { Citation, RetrievedChunk } from "../lib/types";
import { AnimatePresence, motion } from "framer-motion";

import { Button } from "./ui/button";

interface Props {
  citation: Citation | null;
  chunk: RetrievedChunk | null;
  onClose: () => void;
}

import { ScrollArea } from "./ui/scroll-area";

export function SourceDrawer({ citation, chunk, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (citation) {
      closeRef.current?.focus();
    }
  }, [citation]);

  return (
    <AnimatePresence>
      {citation && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 sm:p-6" role="presentation" onClick={onClose}>
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 25 }}
            className="relative w-full max-w-2xl overflow-hidden rounded-3xl border border-border/70 bg-card/85 p-6 shadow-halo backdrop-blur-xl flex flex-col max-h-[85vh]"
            role="dialog"
            aria-modal="true"
            aria-label={`Source for Bhagavad Gita ${citation.chapter}.${citation.verse}`}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <div className="text-xl font-semibold font-[var(--font-heading)] text-accent shadow-sm">
                  Bhagavad Gita {citation.chapter}.{citation.verse}
                </div>
                <div className="mt-1 text-sm text-muted-foreground">
                  {citation.type}
                  {citation.source_pages.length ? ` · page ${citation.source_pages.join(", ")}` : ""}
                </div>
              </div>
              <Button ref={closeRef} onClick={onClose} variant="ghost" size="sm" className="rounded-full hover:bg-accent/10 hover:text-accent transition">
                Close
              </Button>
            </div>
            
            <div className="relative flex-1 overflow-hidden min-h-0">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-6 bg-gradient-to-b from-[hsl(var(--card))] to-transparent z-10" />
              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-6 bg-gradient-to-t from-[hsl(var(--card))] to-transparent z-10" />
              
              <ScrollArea className="h-full pr-4">
                <div className="text-[15px] leading-[1.8] text-foreground/90 font-serif pt-2 pb-6">
                  {chunk?.text || citation.preview || "No source text was returned."}
                </div>
              </ScrollArea>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
