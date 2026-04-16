"use client";

import { useState } from "react";
import type { Citation, RetrievedChunk } from "../lib/types";
import { SourceDrawer } from "./SourceDrawer";

interface Props {
  citations: Citation[];
  chunks: RetrievedChunk[];
}

export function CitationList({ citations, chunks }: Props) {
  const [active, setActive] = useState<Citation | null>(null);

  if (citations.length === 0) {
    return <div className="trust-warning">No valid citations were returned. Treat this answer as unverified.</div>;
  }

  return (
    <>
      <div className="citation-list" aria-label="Verse citations">
        {citations.map((citation) => (
          <button
            key={citation.chunk_id}
            className="citation-chip"
            onClick={() => setActive(citation)}
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
