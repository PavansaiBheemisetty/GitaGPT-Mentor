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
    <form className="relative w-full" onSubmit={submit}>
      <label className="sr-only" htmlFor="chat-input">
        Ask GitaGPT
      </label>
      <div className="rounded-3xl border border-border/80 bg-card/70 p-2 pb-1.5 shadow-halo backdrop-blur-md transition-all focus-within:border-accent/40 focus-within:shadow-[0_0_30px_rgba(255,215,0,0.15)] flex flex-col">
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
        <div className="flex items-center justify-between px-2 pt-1 pb-1">
          <div className="text-xs text-accent/60 opacity-80 min-h-4">
            {isStreaming ? "Listening..." : ""}
          </div>
          <motion.div whileTap={{ scale: 0.9 }}>
            <Button 
              type="submit" 
              disabled={disabled || !value.trim()} 
              size="icon"
              className="rounded-full bg-accent text-accent-foreground hover:bg-accent/90 h-8 w-8 shadow-sm transition-opacity"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          </motion.div>
        </div>
      </div>
    </form>
  );
}
