import type { UiMessage } from "../lib/types";
import { CitationList } from "./CitationList";

export function MessageBubble({ message }: { message: UiMessage }) {
  const response = message.response;
  const trustFailure = response?.warnings.includes("trust_failure_no_valid_citations");
  const status = response
    ? trustFailure
      ? "Trust failure"
      : response.confidence === "sufficient"
        ? `Grounded in ${response.citations.length} passage${response.citations.length === 1 ? "" : "s"}`
        : "Limited context"
    : message.status === "sending"
      ? "Retrieving sources"
      : message.status === "failed"
        ? "Recoverable error"
        : "You";

  return (
    <article className={`message ${message.role} ${message.status || ""}`}>
      <div className="message-status">{status}</div>
      <div className="message-content">{message.content}</div>
      {response ? (
        <>
          <div className="provider-line">
            {response.provider.embedding} · {response.provider.llm} · {response.request_id.slice(0, 8)}
          </div>
          <CitationList citations={response.citations} chunks={response.retrieved_chunks} />
        </>
      ) : null}
    </article>
  );
}
