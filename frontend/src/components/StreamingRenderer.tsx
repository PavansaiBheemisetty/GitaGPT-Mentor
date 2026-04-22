"use client";

import { motion } from "framer-motion";

import { StreamDust } from "./StreamDust";

interface Props {
  content: string;
}

export function StreamingRenderer({ content }: Props) {
  const parts = content.split(/(\s+)/);

  return (
    <div className="relative overflow-hidden rounded-[1.35rem] border border-accent/15 bg-[radial-gradient(circle_at_top_left,rgba(255,215,0,0.08),transparent_32%),linear-gradient(135deg,rgba(10,15,37,0.72),rgba(11,24,58,0.42))] px-4 py-3">
      <StreamDust active />
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-2 left-[-25%] w-[42%] rounded-full bg-[linear-gradient(90deg,transparent,rgba(255,215,0,0.24),rgba(145,192,255,0.16),transparent)] blur-xl"
        animate={{ x: ["0%", "240%"] }}
        transition={{ duration: 2.8, ease: "easeInOut", repeat: Infinity }}
      />
      <div className="relative z-10 whitespace-pre-wrap break-words text-sm leading-[1.8] text-foreground/95 sm:text-[15px]">
        {parts.map((part, index) =>
          /\s+/.test(part) ? (
            part
          ) : (
            <motion.span
              key={`${part}-${index}`}
              className="inline-block will-change-transform"
              initial={{ opacity: 0, filter: "blur(10px)", y: 4, scale: 0.985 }}
              animate={{ opacity: 1, filter: "blur(0px)", y: 0, scale: 1 }}
              transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
            >
              {part}
            </motion.span>
          ),
        )}
        <motion.span
          aria-hidden="true"
          className="ml-1 inline-block h-[1.05em] w-[0.34rem] rounded-full bg-[linear-gradient(180deg,#ffe28c,#9ec5ff)] align-[-0.18em] shadow-[0_0_18px_rgba(255,215,0,0.45)]"
          animate={{ opacity: [0.35, 1, 0.4], scaleY: [0.92, 1.08, 0.92] }}
          transition={{ duration: 1.15, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>
    </div>
  );
}
