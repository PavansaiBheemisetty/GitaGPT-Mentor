import type {
  ChatMessage,
  ChatSession,
  ChatStreamEvent,
  ChatResponse,
  StoredMessage
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const WS_BASE_URL = API_BASE_URL.replace(/^http/, "ws");

function authHeaders(accessToken?: string): HeadersInit {
  if (!accessToken) return { "Content-Type": "application/json" };
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${accessToken}`
  };
}

export async function listSessions(accessToken: string): Promise<ChatSession[]> {
  const response = await fetch(`${API_BASE_URL}/chat/sessions`, {
    method: "GET",
    headers: authHeaders(accessToken)
  });
  if (!response.ok) {
    throw new Error((await safeDetail(response)) || "Could not load chat sessions.");
  }
  return response.json();
}

export async function createSession(accessToken: string, title?: string): Promise<ChatSession> {
  const response = await fetch(`${API_BASE_URL}/chat/sessions`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: JSON.stringify({ title })
  });
  if (!response.ok) {
    throw new Error((await safeDetail(response)) || "Could not create a chat session.");
  }
  return response.json();
}

export async function renameSession(accessToken: string, sessionId: string, title: string): Promise<{status: string, title: string}> {
  const response = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}`, {
    method: "PATCH",
    headers: authHeaders(accessToken),
    body: JSON.stringify({ title })
  });
  if (!response.ok) {
    throw new Error((await safeDetail(response)) || "Could not rename chat session.");
  }
  return response.json();
}

export async function deleteSession(accessToken: string, sessionId: string): Promise<{status: string}> {
  const response = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}`, {
    method: "DELETE",
    headers: authHeaders(accessToken)
  });
  if (!response.ok) {
    throw new Error((await safeDetail(response)) || "Could not delete chat session.");
  }
  return response.json();
}

export async function listSessionMessages(
  accessToken: string,
  sessionId: string
): Promise<StoredMessage[]> {
  const response = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/messages`, {
    method: "GET",
    headers: authHeaders(accessToken)
  });
  if (!response.ok) {
    throw new Error((await safeDetail(response)) || "Could not load session messages.");
  }
  return response.json();
}

export async function sendChat(
  message: string,
  history: ChatMessage[],
  conversationId: string,
  accessToken?: string
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: JSON.stringify({ message, history, top_k: 6, conversation_id: conversationId })
  });

  if (!response.ok) {
    const detail = await safeDetail(response);
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.json();
}

interface StreamChatOptions {
  accessToken?: string;
  message: string;
  conversationId: string;
  topK?: number;
  onEvent: (event: ChatStreamEvent) => void;
  onClose?: () => void;
}

export function streamChat(options: StreamChatOptions): { close: () => void } {
  const socket = new WebSocket(`${WS_BASE_URL}/chat/stream/ws`);

  socket.onopen = () => {
    socket.send(
      JSON.stringify({
        message: options.message,
        conversation_id: options.conversationId,
        top_k: options.topK || 6,
        access_token: options.accessToken || null
      })
    );
  };

  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as ChatStreamEvent;
      options.onEvent(payload);
    } catch {
      options.onEvent({ type: "error", message: "Failed to parse stream event." });
    }
  };

  socket.onerror = () => {
    options.onEvent({ type: "error", message: "Streaming connection failed." });
  };

  socket.onclose = () => {
    options.onClose?.();
  };

  return {
    close: () => {
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close();
      }
    }
  };
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
