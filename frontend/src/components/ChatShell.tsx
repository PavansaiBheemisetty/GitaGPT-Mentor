"use client";

import { useMemo, useState } from "react";
import { sendChat } from "../lib/api";
import type { ChatMessage, UiMessage } from "../lib/types";
import { ChatComposer } from "./ChatComposer";
import { EmptyState } from "./EmptyState";
import { MessageList } from "./MessageList";

const starters = [
  "How can I stay calm under pressure?",
  "What does the Gita say about doing my duty?",
  "How should I deal with anger?"
];

export function ChatShell() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId] = useState(() => crypto.randomUUID());

  const history: ChatMessage[] = useMemo(
    () =>
      messages
        .filter((message) => message.role === "user" || message.response)
        .slice(-6)
        .map((message) => ({
          role: message.role,
          content: message.role === "assistant" ? message.response?.answer || message.content : message.content
        })),
    [messages]
  );

  async function submit(text: string) {
    const content = text.trim();
    if (!content || isSending) return;

    const userMessage: UiMessage = { id: crypto.randomUUID(), role: "user", content };
    const assistantId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      userMessage,
      { id: assistantId, role: "assistant", content: "Thinking...", status: "sending" }
    ]);
    setDraft("");
    setError(null);
    setIsSending(true);

    try {
      const response = await sendChat(content, history, conversationId);
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? { ...message, content: response.answer, response, status: undefined }
            : message
        )
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      setDraft(content);
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantId
            ? {
                ...item,
                content: "I could not reach the GitaGPT backend. Your draft is still in the composer.",
                status: "failed"
              }
            : item
        )
      );
    } finally {
      setIsSending(false);
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Recent chats">
        <div className="brand">GitaGPT</div>
        <div className="sidebar-label">Study prompts</div>
        {starters.map((starter) => (
          <button key={starter} className="history-button" onClick={() => setDraft(starter)}>
            {starter}
          </button>
        ))}
      </aside>
      <section className="chat-panel" aria-label="GitaGPT chat">
        <header className="chat-header">
          <div>
            <h1>GitaGPT</h1>
            <p>Grounded answers with verse references and source previews.</p>
          </div>
          <div className="provider-pill">Local-first RAG</div>
        </header>
        {messages.length === 0 ? (
          <EmptyState onPick={setDraft} prompts={starters} />
        ) : (
          <MessageList messages={messages} />
        )}
        <div aria-live="polite" className="error-line">
          {error}
        </div>
        <ChatComposer value={draft} onChange={setDraft} onSubmit={submit} disabled={isSending} />
      </section>
    </main>
  );
}
