"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import type { Citation, RetrievedChunk } from "../lib/types";
import { AnimatePresence, motion } from "framer-motion";
import { Button } from "./ui/button";

interface Props {
  citation: Citation | null;
  chunk: RetrievedChunk | null;
  onClose: () => void;
}

/**
 * Ancient Scripture Reveal — premium citation modal.
 *
 * On first open the panel "unrolls" like a sacred manuscript with
 * staggered line-by-line text reveal. Subsequent citation switches
 * use a fast content-swap so the user isn't forced to wait.
 */
export function SourceDrawer({ citation, chunk, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const hasOpenedOnce = useRef(false);
  const [isFirstReveal, setIsFirstReveal] = useState(true);

  useEffect(() => {
    if (citation) {
      closeRef.current?.focus();
      if (hasOpenedOnce.current) {
        setIsFirstReveal(false);
      } else {
        setIsFirstReveal(true);
        hasOpenedOnce.current = true;
      }
    }
  }, [citation]);

  // Split body text into lines/sentences for staggered reveal
  const bodyText = chunk?.text || citation?.preview || "No source text was returned.";
  const textLines = useMemo(() => {
    // Split on sentence boundaries or newlines
    return bodyText
      .split(/(?<=[.!?।॥])\s+|\n+/)
      .filter((line) => line.trim().length > 0);
  }, [bodyText]);

  // Animation variants
  const firstOpenDuration = 0.7;
  const quickSwapDuration = 0.25;

  return (
    <AnimatePresence>
      {citation && (
        /* Backdrop with warm vignette */
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6"
          role="presentation"
          onClick={onClose}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
        >
          {/* Dark backdrop with warm radial vignette */}
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse at center, rgba(255,200,80,0.06) 0%, transparent 70%)",
            }}
          />

          {/* Scripture Panel */}
          <motion.div
            initial={{
              scaleY: isFirstReveal ? 0.02 : 0.95,
              scaleX: isFirstReveal ? 0.7 : 0.98,
              opacity: isFirstReveal ? 0 : 0.5,
            }}
            animate={{ scaleY: 1, scaleX: 1, opacity: 1 }}
            exit={{
              scaleY: 0.02,
              scaleX: 0.7,
              opacity: 0,
            }}
            transition={{
              duration: isFirstReveal ? firstOpenDuration : quickSwapDuration,
              ease: [0.22, 1, 0.36, 1],
            }}
            className="scripture-panel relative flex w-[95vw] max-w-2xl origin-top flex-col overflow-hidden rounded-2xl"
            style={{
              maxHeight: "min(85vh, calc(100dvh - 3rem))",
              /* Parchment-inspired background with deep navy/warm tone */
              background: `
                linear-gradient(180deg,
                  rgba(28, 22, 12, 0.97) 0%,
                  rgba(18, 14, 8, 0.98) 40%,
                  rgba(22, 18, 10, 0.97) 100%
                )
              `,
              /* Warm lamp-like edge glow */
              boxShadow: `
                0 0 80px rgba(255, 200, 80, 0.12),
                0 0 40px rgba(255, 200, 80, 0.06),
                inset 0 1px 0 rgba(255, 215, 0, 0.15),
                inset 0 -1px 0 rgba(255, 215, 0, 0.08)
              `,
            }}
            role="dialog"
            aria-modal="true"
            aria-label={`Source for Bhagavad Gita ${citation.chapter}.${citation.verse}`}
            onClick={(event) => event.stopPropagation()}
          >
            {/* Gold embossed double border */}
            <div
              className="pointer-events-none absolute inset-0 rounded-2xl"
              style={{
                border: "1px solid rgba(255, 200, 80, 0.25)",
                boxShadow: "inset 0 0 0 3px rgba(255, 200, 80, 0.06)",
              }}
            />

            {/* Sanskrit watermark */}
            <div
              className="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden opacity-[0.025]"
              aria-hidden="true"
            >
              <span
                className="select-none text-[12rem] leading-none tracking-wider"
                style={{ fontFamily: "serif", color: "rgba(255, 215, 0, 1)" }}
              >
                ॐ
              </span>
            </div>

            {/* Aged parchment texture overlay */}
            <div
              className="pointer-events-none absolute inset-0 rounded-2xl opacity-[0.04]"
              style={{
                backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
              }}
            />

            {/* Subtle side vignette for cinematic depth */}
            <div
              className="pointer-events-none absolute inset-0 z-[1] rounded-2xl"
              style={{
                boxShadow: "inset 18px 0 30px -12px rgba(0,0,0,0.3), inset -18px 0 30px -12px rgba(0,0,0,0.3), inset 0 12px 20px -8px rgba(0,0,0,0.2), inset 0 -12px 20px -8px rgba(0,0,0,0.2)",
              }}
            />

            {/* Header */}
            <motion.div
              className="relative z-10 px-6 pb-4 pt-6 sm:px-8 sm:pt-8"
              initial={{ opacity: 0, y: isFirstReveal ? 10 : 0 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                delay: isFirstReveal ? 0.35 : 0,
                duration: isFirstReveal ? 0.5 : 0.2,
              }}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  {/* Title in Cinzel serif */}
                  <h2
                    className="text-2xl font-semibold tracking-wide sm:text-[1.65rem]"
                    style={{
                      fontFamily: "var(--font-heading), Cinzel, serif",
                      color: "rgba(255, 215, 100, 0.9)",
                      textShadow: "0 0 20px rgba(255, 200, 80, 0.15)",
                    }}
                  >
                    Bhagavad Gita {citation.chapter}.{citation.verse}
                  </h2>

                  {/* Subtitle */}
                  <div
                    className="mt-1.5 text-sm tracking-wider"
                    style={{
                      fontFamily: "var(--font-heading), Cinzel, serif",
                      color: "rgba(255, 215, 100, 0.4)",
                      letterSpacing: "0.12em",
                    }}
                  >
                    {citation.type}
                    {citation.source_pages.length > 0
                      ? ` · page ${citation.source_pages.join(", ")}`
                      : ""}
                  </div>
                </div>

                <Button
                  ref={closeRef}
                  onClick={onClose}
                  variant="ghost"
                  size="sm"
                  className="rounded-full border border-amber-400/20 text-amber-200/60 transition hover:border-amber-400/40 hover:bg-amber-400/10 hover:text-amber-200"
                >
                  Close
                </Button>
              </div>

              {/* Gold separator line */}
              <motion.div
                className="mt-4 h-px"
                style={{
                  background:
                    "linear-gradient(90deg, transparent, rgba(255, 200, 80, 0.3), rgba(255, 200, 80, 0.5), rgba(255, 200, 80, 0.3), transparent)",
                }}
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{
                  delay: isFirstReveal ? 0.5 : 0,
                  duration: isFirstReveal ? 0.5 : 0.2,
                  ease: "easeOut",
                }}
              />
            </motion.div>

            {/* Body text — staggered line reveal */}
            <div className="relative min-h-0 flex-1 overflow-hidden px-5 pb-5 sm:px-8 sm:pb-8">
              {/* Scroll fade edges */}
              <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-4 bg-gradient-to-b from-[rgba(22,18,10,0.97)] to-transparent" />
              <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-6 bg-gradient-to-t from-[rgba(22,18,10,0.97)] to-transparent" />

              <div className="h-full overflow-y-auto overscroll-contain pr-3 scripture-scroll">
                <div className="space-y-3 pb-4 pt-2">
                  {textLines.map((line, index) => (
                    <motion.p
                      key={`${citation.chunk_id}-${index}`}
                      className="text-[15px] leading-[1.9] sm:text-base"
                      style={{
                        fontFamily: "'Georgia', 'Times New Roman', serif",
                        color: "rgba(230, 220, 200, 0.88)",
                      }}
                      initial={{
                        opacity: 0,
                        y: isFirstReveal ? 6 : 0,
                        filter: isFirstReveal
                          ? "blur(4px) brightness(1.4)"
                          : "blur(0px)",
                      }}
                      animate={{
                        opacity: 1,
                        y: 0,
                        filter: "blur(0px) brightness(1)",
                      }}
                      transition={{
                        delay: isFirstReveal
                          ? 0.55 + index * 0.08
                          : 0.05 + index * 0.02,
                        duration: isFirstReveal ? 0.5 : 0.2,
                        ease: "easeOut",
                      }}
                    >
                      {line}
                    </motion.p>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
