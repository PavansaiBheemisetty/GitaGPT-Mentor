import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

import type { UiMessage } from "../lib/types";
import { CitationList } from "./CitationList";
import { StreamDust } from "./StreamDust";

const WAITING_PHRASES = [
  "Listening to your question...",
  "Reflecting with clarity...",
  "Finding the right words...",
  "Aligning thought and action...",
  "Letting insight emerge...",
  "Translating wisdom into guidance..."
];

const PUNCHLINE_MARKER = "@@PUNCHLINE@@";

function ThinkingIndicator() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((current) => (current + 1) % WAITING_PHRASES.length);
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex h-6 items-center overflow-hidden text-[13px] text-muted-foreground/80 italic">
      <AnimatePresence mode="popLayout">
        <motion.span
          key={index}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.4 }}
        >
          {WAITING_PHRASES[index]}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}

function normalizeAssistantMarkdown(content: string) {
  let normalized = content.replace(/\r\n/g, "\n");

  // Strip malformed markdown artifacts: "**.", "*.", standalone "**" lines
  normalized = normalized.replace(/\*{1,3}\.(?:\s|$)/g, "");
  normalized = normalized.replace(/^\s*\*{2,3}\s*$/gm, "");

  // Strip bold-wrapping from known section headings so they match the map below.
  // Handles: **Direct Insight**, **1. Direct Insight (Human Tone)**, etc.
  normalized = normalized.replace(
    /\*\*\s*((?:\d+\.\s*)?(?:Direct Insight|Gita Wisdom|Why This Happens|Practical Reflection|Closing Line)[^*]*)\*\*/g,
    "$1"
  );

  // Recover malformed outputs where section headings are inline in one paragraph.
  normalized = normalized.replace(
    /((?:\d+\.\s*)?(?:Direct Insight|Gita Wisdom|Why This Happens|Practical Reflection|Closing Line)(?:\s*\([^)]*\))?)\s*:?\s*/g,
    "\n\n$1\n"
  );

  // Headings with full subtitles preserved for display
  const sectionMap = new Map([
    ["1. Direct Insight (Human Tone)", "### Direct Insight (Human Tone)"],
    ["Direct Insight (Human Tone)", "### Direct Insight (Human Tone)"],
    ["Direct Insight", "### Direct Insight (Human Tone)"],
    ["2. Gita Wisdom (Verse Reference + Meaning)", "### Gita Wisdom (Verse Reference + Meaning)"],
    ["Gita Wisdom (Verse Reference + Meaning)", "### Gita Wisdom (Verse Reference + Meaning)"],
    ["Gita Wisdom", "### Gita Wisdom (Verse Reference + Meaning)"],
    ["3. Why This Happens (Mechanism)", "### Why This Happens (Mechanism)"],
    ["Why This Happens (Mechanism)", "### Why This Happens (Mechanism)"],
    ["Why This Happens", "### Why This Happens (Mechanism)"],
    ["4. Practical Reflection (Actionable Steps)", "### Practical Reflection (Actionable Steps)"],
    ["Practical Reflection (Actionable Steps)", "### Practical Reflection (Actionable Steps)"],
    ["Practical Reflection", "### Practical Reflection (Actionable Steps)"],
  ]);

  // "Closing Line" variants → no heading, just mark punchline
  const closingLabels = new Set([
    "Closing Line (Punchline)",
    "5. Closing Line (Punchline)",
    "Closing Line",
  ]);

  const lines = normalized.split("\n");
  const output: string[] = [];
  let skipNextAsPunchline = false;

  for (let index = 0; index < lines.length; index += 1) {
    const raw = lines[index].trim();
    if (!raw) {
      output.push("");
      continue;
    }

    let line = raw;
    // Fix malformed markers such as "**. text" or "** text" that may leak from model formatting.
    line = line.replace(/^\*{1,3}\s*[.:]\s*/, "").trim();
    line = line.replace(/^\*{2,3}\s+(?=\S)/, "").trim();
    if (!line) {
      continue;
    }

    // Remove markdown noise lines that create visible dot/bullet artifacts.
    if (line === "." || line === "-" || line === "*" || line === "•") {
      continue;
    }

    if (/^(?:[-*•]\s*)[.]?$/.test(line)) {
      continue;
    }

    if (/^(?:[-*•]\s+)$/.test(line)) {
      continue;
    }

    if (/^(?:[-*•]\s*)(?:\.|\*)$/.test(line)) {
      continue;
    }

    // If previous line was a closing label, this line IS the punchline text
    if (skipNextAsPunchline) {
      skipNextAsPunchline = false;
      const punchText = line.replace(/^\*+|\*+$/g, "").trim();
      if (punchText) {
        output.push("");
        output.push(`${PUNCHLINE_MARKER} ${punchText}`);
      }
      continue;
    }

    const punchlineMatch = line.match(/^closing punchline\s*:?\s*(.*)$/i);
    if (punchlineMatch) {
      const punchline = punchlineMatch[1].trim();
      if (punchline) {
        output.push("");
        output.push(`${PUNCHLINE_MARKER} ${punchline}`);
      }
      continue;
    }

    // Check for closing label (strip trailing colon/period too)
    const rawCleaned = line.replace(/[:.]$/, "").trim();
    if (closingLabels.has(line) || closingLabels.has(rawCleaned)) {
      // Next non-empty line is the punchline — skip the label entirely
      skipNextAsPunchline = true;
      continue;
    }

    // Try exact match first
    let sectionHeading = sectionMap.get(line);
    // Also try stripping trailing colon or period
    if (!sectionHeading) {
      sectionHeading = sectionMap.get(rawCleaned);
    }
    if (sectionHeading) {
      // Ensure blank line before heading for proper markdown separation
      if (output.length > 0 && output[output.length - 1] !== "") {
        output.push("");
      }
      output.push(sectionHeading);
      output.push("");
      continue;
    }

    const isLastLine = index === lines.length - 1;
    const looksLikeParagraph = !line.startsWith("-") && !line.startsWith("*") && !line.startsWith(">") && !/^#{1,6}\s/.test(line);
    if (isLastLine && looksLikeParagraph) {
      // Strip italic markdown from punchline
      const punchText = line.replace(/^\*+|\*+$/g, "").trim();
      output.push("");
      output.push(`${PUNCHLINE_MARKER} ${punchText}`);
      continue;
    }

    output.push(line);
  }

  // Collapse triple+ blank lines into double blank lines
  let result = output.join("\n");
  result = result.replace(/\n{3,}/g, "\n\n");

  return result;
}

const markdownComponents: Components = {
  h2: ({ children }) => (
    <h2 className="mt-4 mb-2 text-[1.05rem] font-semibold text-foreground font-[var(--font-heading)] sm:text-[1.125rem] border-l-2 border-accent/50 pl-3">
      {children}
    </h2>
  ),
  h3: ({ children }) => {
    // Render subtitle portion in a softer color
    const text = Array.isArray(children)
      ? children.map((c) => (typeof c === "string" ? c : "")).join("")
      : typeof children === "string" ? children : "";
    const match = text.match(/^(.+?)\s*(\([^)]+\))$/);
    if (match) {
      return (
        <h3 className="mt-4 mb-2 text-[1.05rem] font-semibold text-foreground font-[var(--font-heading)] sm:text-[1.125rem] border-l-2 border-accent/40 pl-3">
          {match[1]}{" "}
          <span className="text-[0.8rem] font-medium text-muted-foreground/80">{match[2]}</span>
        </h3>
      );
    }
    return (
      <h3 className="mt-4 mb-2 text-[1.05rem] font-semibold text-foreground font-[var(--font-heading)] sm:text-[1.125rem] border-l-2 border-accent/40 pl-3">
        {children}
      </h3>
    );
  },
  p: ({ children }) => {
    const textContent = Array.isArray(children)
      ? children.map((child) => (typeof child === "string" ? child : "")).join("")
      : typeof children === "string"
        ? children
        : "";
    const isPunchline = textContent.trim().startsWith(PUNCHLINE_MARKER);
    const cleaned = isPunchline ? textContent.replace(PUNCHLINE_MARKER, "").trim() : null;
    return (
      <p
        className={
          isPunchline
            ? "mt-4 mb-0 text-[15px] leading-[1.6] font-semibold text-white/95 sm:text-base"
            : "mb-[10px] text-sm leading-[1.6] text-foreground/92 sm:text-[15px]"
        }
      >
        {isPunchline ? cleaned : children}
      </p>
    );
  },
  ul: ({ children }) => (
    <ul className="mt-2 mb-3 list-disc space-y-1.5 pl-[18px] text-sm leading-[1.6] text-foreground/92 sm:text-[15px]">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-4 list-decimal space-y-2 pl-5 text-sm leading-7 text-foreground/92 sm:text-[15px]">{children}</ol>
  ),
  li: ({ children }) => <li className="pl-1">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
  blockquote: ({ children }) => (
    <blockquote className="my-5 rounded-2xl border border-accent/20 bg-accent/8 px-4 py-3 text-[15px] leading-7 text-foreground shadow-sm">
      {children}
    </blockquote>
  )
};

export function MessageBubble({ message }: { message: UiMessage }) {
  const response = message.response;
  const trustFailure = response?.warnings.includes("trust_failure_no_valid_citations");
  const statusText = response
    ? trustFailure
      ? "Trust failure"
      : response.confidence === "sufficient"
        ? `Grounded in ${response.citations.length} passage${response.citations.length === 1 ? "" : "s"}`
        : "Limited context"
    : message.status === "thinking"
      ? ""
      : message.status === "streaming"
        ? "Streaming"
        : message.status === "failed"
          ? "Recoverable error"
          : "You";

  const isAssistant = message.role === "assistant";
  const isStreaming = message.status === "streaming";
  const renderedMarkdown = isAssistant ? normalizeAssistantMarkdown(message.content) : message.content;

  return (
    <article
      className={`relative w-full rounded-2xl border px-5 py-4 shadow-sm backdrop-blur-sm transition-all ${
        isAssistant
          ? "border-border/60 bg-card/60 text-foreground"
          : "border-white/10 bg-[linear-gradient(135deg,rgba(17,23,54,0.94),rgba(24,30,66,0.92))] text-white"
      } ${message.status === "failed" ? "border-rose-300/40" : ""}`}
    >
      {statusText && <div className="mb-2 text-[11px] uppercase tracking-[0.16em] text-accent/80">{statusText}</div>}

      {message.status === "thinking" ? (
        <ThinkingIndicator />
      ) : (
        <div className={`message-container markdown-content break-words text-sm sm:text-[15px] ${isAssistant ? "opacity-90" : "opacity-100 font-normal"}`}>
          <div className="flex flex-col">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {renderedMarkdown}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {isAssistant && <StreamDust active={isStreaming} />}

      {response ? (
        <>
          <div className="mb-2 mt-4 h-px w-full bg-border/40" />
          <CitationList citations={response.citations} chunks={response.retrieved_chunks} />
        </>
      ) : null}
    </article>
  );
}
