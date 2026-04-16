import type { ChatMessage, ChatResponse } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function sendChat(
  message: string,
  history: ChatMessage[],
  conversationId: string
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, top_k: 6, conversation_id: conversationId })
  });

  if (!response.ok) {
    const detail = await safeDetail(response);
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.json();
}

async function safeDetail(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    if (data.detail?.message) {
      return [data.detail.message, data.detail.fix].filter(Boolean).join(" ");
    }
  } catch {
    return "";
  }
  return "";
}
