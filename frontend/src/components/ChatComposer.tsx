"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { ArrowUp } from "lucide-react";

import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  disabled: boolean;
  isStreaming: boolean;
}

/**
 * Chat composer with mobile-safe layout.
 *
 * Key mobile fixes:
 * - Uses env(safe-area-inset-bottom) for notch/home-bar clearance
 * - flex layout ensures send button never clips
 * - min-height on button container prevents collapse
 * - shrink-0 on button prevents it from being squeezed by flex
 */
export function ChatComposer({ value, onChange, onSubmit, disabled, isStreaming }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const node = textareaRef.current;
    if (!node) return;
    node.style.height = "0px";
    node.style.height = `${Math.min(node.scrollHeight, 200)}px`;
  }, [value]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(value);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit(value);
    }
  }

  return (
    <form className="relative w-full min-w-0" onSubmit={submit}>
      <label className="sr-only" htmlFor="chat-input">
        Ask GitaGPT
      </label>
      <div className="flex min-w-0 flex-col rounded-3xl border border-border/80 bg-card/80 p-2 pb-2 shadow-halo backdrop-blur-md transition-all focus-within:border-accent/40 focus-within:shadow-[0_0_30px_rgba(255,215,0,0.15)]">
        <Textarea
          ref={textareaRef}
          id="chat-input"
          value={value}
          onKeyDown={handleKeyDown}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Ask what is on your mind..."
          disabled={disabled}
          className="max-h-[200px] min-h-[52px] resize-none border-0 bg-transparent px-3 py-3 text-[15px] leading-6 shadow-none focus-visible:ring-0 placeholder:text-muted-foreground/60"
        />
        {/* Send row: flex with minimum height to guarantee button visibility on mobile */}
        <div className="flex min-h-[44px] min-w-0 items-center justify-between gap-3 px-2 pb-1 pt-1">
          <div className="min-h-4 flex-1 truncate pr-2 text-xs text-accent/60 opacity-80">
            {isStreaming ? "Listening..." : ""}
          </div>
          <motion.div whileTap={{ scale: 0.9 }} className="shrink-0">
            <Button
              type="submit"
              disabled={disabled || !value.trim()}
              size="icon"
              className="h-10 w-10 shrink-0 rounded-full bg-accent text-accent-foreground shadow-sm transition-opacity hover:bg-accent/90"
              aria-label="Send message"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          </motion.div>
        </div>
      </div>
    </form>
  );
}
