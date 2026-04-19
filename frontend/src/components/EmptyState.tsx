"use client";

import { motion } from "framer-motion";

interface Props {
  prompts: string[];
  onPick: (prompt: string) => void;
}

export function EmptyState({ prompts, onPick }: Props) {
  return (
    <section className="mx-auto w-full max-w-3xl px-4 py-8 sm:py-14">
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45 }}
        className="rounded-3xl border border-border/70 bg-card/55 p-7 shadow-halo backdrop-blur-sm"
      >
        <p className="text-xs uppercase tracking-[0.22em] text-accent">Calm Guidance</p>
        <h2 className="mt-2 text-3xl font-semibold leading-tight text-foreground sm:text-4xl">
          Ask what is weighing on you. Get grounded direction with verifiable verses.
        </h2>
        <p className="mt-3 text-sm leading-7 text-muted-foreground sm:text-base">
          This mentor mode is optimized for pressure moments. Focus on one situation, then continue follow-up turns in the same chat.
        </p>
      </motion.div>
      <div className="mt-5 grid gap-2.5 sm:grid-cols-2">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onPick(prompt)}
            className="rounded-2xl border border-border/70 bg-card/60 px-4 py-3 text-left text-sm text-foreground transition hover:border-accent/40 hover:bg-card"
          >
            {prompt}
          </button>
        ))}
      </div>
    </section>
  );
}
