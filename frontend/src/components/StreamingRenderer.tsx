"use client";

import { useRef } from "react";
import { motion } from "framer-motion";
import { StreamDust } from "./StreamDust";

interface Props {
  content: string;
}

/**
 * Renders streaming text with a divine dust-forming effect.
 * Each word appears with a blur→sharpen animation as if golden dust
 * is materializing into letters. The StreamDust canvas tracks the cursor
 * and emits particles from its current position.
 */
export function StreamingRenderer({ content }: Props) {
  const parts = content.split(/(\s+)/);
  const cursorRef = useRef<HTMLSpanElement>(null);

  return (
    <div className="streaming-bubble relative overflow-hidden rounded-[1.35rem] border border-accent/15 bg-[radial-gradient(circle_at_top_left,rgba(255,215,0,0.06),transparent_32%),linear-gradient(135deg,rgba(10,15,37,0.72),rgba(11,24,58,0.42))] px-4 py-3">
      <StreamDust active cursorRef={cursorRef} />

      {/* Text with dust-reveal effect */}
      <div className="relative z-10 whitespace-pre-wrap break-words text-sm leading-[1.8] text-foreground/95 sm:text-[15px]">
        {parts.map((part, index) =>
          /\s+/.test(part) ? (
            part
          ) : (
            <motion.span
              key={`${part}-${index}`}
              className="dust-word inline-block will-change-[opacity,filter,transform]"
              initial={{
                opacity: 0,
                filter: "blur(8px) brightness(1.8)",
                y: 4,
              }}
              animate={{
                opacity: 1,
                filter: "blur(0px) brightness(1)",
                y: 0,
              }}
              transition={{
                duration: 0.4,
                ease: "easeOut",
              }}
            >
              {part}
            </motion.span>
          ),
        )}

        {/* Pulsing golden orb cursor */}
        <motion.span
          ref={cursorRef}
          aria-hidden="true"
          className="ml-[0.3em] inline-block h-[0.4em] w-[0.4em] rounded-full bg-amber-100/40"
          animate={{
            opacity: [0.2, 0.6, 0.2],
            scale: [0.9, 1.05, 0.9],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      </div>
    </div>
  );
}
