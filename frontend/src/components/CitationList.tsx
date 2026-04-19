"use client";

import { useState } from "react";
import type { Citation, RetrievedChunk } from "../lib/types";
import { SourceDrawer } from "./SourceDrawer";

interface Props {
  citations: Citation[];
  chunks: RetrievedChunk[];
  onOpenCitation?: () => void;
}

export function CitationList({ citations, chunks, onOpenCitation }: Props) {
  const [active, setActive] = useState<Citation | null>(null);

  if (citations.length === 0) {
    return (
      <div className="mt-3 rounded-xl border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs text-amber-100">
        No valid citations were returned. Treat this answer as unverified.
      </div>
    );
  }

  return (
    <>
      <div className="mt-4 flex flex-wrap gap-2" aria-label="Verse citations">
        {citations.map((citation) => (
          <button
            key={citation.chunk_id}
            className="rounded-full border border-accent/40 bg-accent/10 px-4 py-1.5 text-[12px] font-medium text-accent/90 transition-all hover:bg-accent/20 hover:border-accent/60 hover:shadow-[0_0_12px_rgba(255,215,0,0.15)] flex items-center gap-1.5"
            onClick={() => {
              setActive(citation);
              onOpenCitation?.();
            }}
            aria-label={`Open source for Bhagavad Gita ${citation.chapter}.${citation.verse} ${citation.type}`}
          >
            BG {citation.chapter}.{citation.verse} {citation.type}
          </button>
        ))}
      </div>
      <SourceDrawer
        citation={active}
        chunk={chunks.find((chunk) => chunk.chunk_id === active?.chunk_id) || null}
        onClose={() => setActive(null)}
      />
    </>
  );
}
