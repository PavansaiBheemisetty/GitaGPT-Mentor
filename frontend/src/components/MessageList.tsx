"use client";

import { motion } from "framer-motion";

import type { UiMessage } from "../lib/types";
import { MessageBubble } from "./MessageBubble";

export function MessageList({ messages }: { messages: UiMessage[] }) {
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 pb-10 pt-5 sm:px-6" aria-live="polite">
      {messages.map((message) => (
        <motion.div
          key={message.id}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className={`flex w-full ${message.role === "assistant" ? "justify-start" : "justify-end"}`}
        >
          <div className={`w-full max-w-[90%] sm:max-w-[80%]`}>
            <MessageBubble message={message} />
          </div>
        </motion.div>
      ))}
    </div>
  );
}
