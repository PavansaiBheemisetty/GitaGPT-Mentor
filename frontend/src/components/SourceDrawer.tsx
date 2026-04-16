"use client";

import { useEffect, useRef } from "react";
import type { Citation, RetrievedChunk } from "../lib/types";

interface Props {
  citation: Citation | null;
  chunk: RetrievedChunk | null;
  onClose: () => void;
}

export function SourceDrawer({ citation, chunk, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (citation) {
      closeRef.current?.focus();
    }
  }, [citation]);

  if (!citation) return null;

  return (
    <div className="drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        className="source-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`Source for Bhagavad Gita ${citation.chapter}.${citation.verse}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="drawer-header">
          <div>
            <div className="drawer-title">
              Bhagavad Gita {citation.chapter}.{citation.verse}
            </div>
            <div className="drawer-subtitle">
              {citation.type}
              {citation.source_pages.length ? ` · page ${citation.source_pages.join(", ")}` : ""}
              {typeof citation.score === "number" ? ` · score ${citation.score.toFixed(2)}` : ""}
            </div>
          </div>
          <button ref={closeRef} onClick={onClose}>
            Close
          </button>
        </div>
        <pre className="source-text">{chunk?.text || citation.preview || "No source text was returned."}</pre>
      </aside>
    </div>
  );
}
