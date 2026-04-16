import type { UiMessage } from "../lib/types";
import { MessageBubble } from "./MessageBubble";

export function MessageList({ messages }: { messages: UiMessage[] }) {
  return (
    <div className="messages" aria-live="polite">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
    </div>
  );
}
