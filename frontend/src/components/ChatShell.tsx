"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, Edit2, LogOut, Menu, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { User } from "@supabase/supabase-js";

import {
  createSession,
  deleteSession,
  listSessionMessages,
  listSessions,
  renameSession,
  streamChat
} from "../lib/api";
import { getSupabaseClient } from "../lib/supabase";
import type { ChatSession, StoredMessage, UiMessage } from "../lib/types";
import { ChatComposer } from "./ChatComposer";
import { EmptyState } from "./EmptyState";
import { MessageList } from "./MessageList";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";

const starters = [
  "How can I stay calm under pressure?",
  "What does the Gita say about doing my duty?",
  "How should I deal with anger?"
];

export function ChatShell() {
  const supabase = useMemo(() => getSupabaseClient(), []);
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [guestConversationId, setGuestConversationId] = useState(() => crypto.randomUUID());
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emailInput, setEmailInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [authNotice, setAuthNotice] = useState<string | null>(null);
  const [isAuthSubmitting, setIsAuthSubmitting] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [isHydrating, setIsHydrating] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");

  const viewportRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const shouldStickToBottom = useRef(true);

  useEffect(() => {
    const syncViewport = () => {
      document.documentElement.style.setProperty("--app-height", `${window.innerHeight}px`);
    };
    syncViewport();
    if (window.innerWidth < 768) {
      setIsSidebarOpen(false);
    }
    window.addEventListener("resize", syncViewport);
    window.visualViewport?.addEventListener("resize", syncViewport);
    return () => {
      window.removeEventListener("resize", syncViewport);
      window.visualViewport?.removeEventListener("resize", syncViewport);
    };
  }, []);

  useEffect(() => {
    if (!supabase) {
      setIsHydrating(false);
      return;
    }
    const init = async () => {
      const {
        data: { session }
      } = await supabase.auth.getSession();
      setUser(session?.user || null);
      setAccessToken(session?.access_token || null);
      setIsHydrating(false);
    };
    init();

    const {
      data: { subscription }
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user || null);
      setAccessToken(session?.access_token || null);
    });
    return () => subscription.unsubscribe();
  }, [supabase]);

  const loadSessions = useCallback(async (token: string) => {
    try {
      const data = await listSessions(token);
      setSessions(data);
      setActiveSessionId((current) => current ?? data[0]?.id ?? null);
    } catch (err) {
      setError(reportAndSoftenError("sessions:list", err, "Could not load sessions."));
    }
  }, []);

  const loadMessages = useCallback(async (token: string, sessionId: string) => {
    try {
      const data = await listSessionMessages(token, sessionId);
      setMessages(data.map(toUiMessage));
    } catch (err) {
      setError(reportAndSoftenError("messages:list", err, "Could not load conversation."));
    }
  }, []);

  useEffect(() => {
    if (!accessToken) {
      setSessions([]);
      setActiveSessionId(null);
      setMessages([]);
      return;
    }
    loadSessions(accessToken);
  }, [accessToken, loadSessions]);

  useEffect(() => {
    if (!accessToken || !activeSessionId) {
      setMessages([]);
      return;
    }
    loadMessages(accessToken, activeSessionId);
  }, [accessToken, activeSessionId, loadMessages]);

  useEffect(() => {
    if (!shouldStickToBottom.current) return;
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  useEffect(() => {
    const defaultTitle = "GitaGPT — Divine Guidance";
    if (isStreaming) {
      document.title = "✨ Receiving Divine Guidance...";
      return;
    }

    const latestUserQuestion = [...messages]
      .reverse()
      .find((message) => message.role === "user" && message.content.trim())
      ?.content.trim();

    if (!latestUserQuestion) {
      document.title = defaultTitle;
      return;
    }

    const compact = latestUserQuestion.length > 68
      ? `${latestUserQuestion.slice(0, 65).trimEnd()}...`
      : latestUserQuestion;
    document.title = `${compact} | GitaGPT`;
  }, [isStreaming, messages]);



  async function ensureSession(): Promise<string> {
    if (!accessToken) return guestConversationId;
    if (activeSessionId) return activeSessionId;
    const session = await createSession(accessToken, "New Chat");
    setSessions((current) => [session, ...current]);
    setActiveSessionId(session.id);
    return session.id;
  }

  async function createNewChat() {
    if (!accessToken) {
      if (supabase) return;
      setGuestConversationId(crypto.randomUUID());
      setMessages([]);
      setDraft("");
      setError(null);
      return;
    }
    try {
      const session = await createSession(accessToken, "New Chat");
      setSessions((current) => [session, ...current]);
      setActiveSessionId(session.id);
      setMessages([]);
      setDraft("");
      setError(null);
    } catch (err) {
      setError(reportAndSoftenError("sessions:create", err, "Could not create chat."));
    }
  }

  async function handleRename(sessionId: string) {
    if (!editingTitle.trim() || !accessToken) return;
    try {
      await renameSession(accessToken, sessionId, editingTitle.trim());
      setSessions((current) =>
        current.map((s) => (s.id === sessionId ? { ...s, title: editingTitle.trim() } : s))
      );
    } catch {
      setError("Could not rename session.");
    }
    setEditingSessionId(null);
  }

  async function handleDeleteSession(sessionId: string) {
    if (!accessToken) return;
    const confirmDelete = window.confirm("Delete this session?");
    if (!confirmDelete) return;

    const wasActive = activeSessionId === sessionId;

    try {
      await deleteSession(accessToken, sessionId);

      setSessions((current) => current.filter((session) => session.id !== sessionId));
      if (wasActive) {
        setActiveSessionId(null);
        setMessages([]);
        setDraft("");

        const freshSession = await createSession(accessToken, "New Chat");
        setSessions((current) => [freshSession, ...current]);
        setActiveSessionId(freshSession.id);
      }

      if (wasActive) {
        setEditingSessionId(null);
      }
    } catch (err) {
      setError(reportAndSoftenError("sessions:delete", err, "Could not delete session."));
    }
  }

  function onScrollMessages() {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const gap = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
    shouldStickToBottom.current = gap < 120;
  }

  async function signInWithGoogle() {
    if (!supabase) return;
    setAuthNotice(null);
    setIsAuthSubmitting(true);
    const origin = window.location.origin;
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: origin }
    });
    if (oauthError) {
      setAuthNotice(readableAuthError(oauthError.message));
    }
    setIsAuthSubmitting(false);
  }

  async function handlePasswordAuth() {
    if (!supabase) return;
    const email = emailInput.trim();
    const password = passwordInput.trim();
    if (!email || !password) return;
    setAuthNotice(null);
    setIsAuthSubmitting(true);

    if (isSignUp) {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) {
        setAuthNotice(readableAuthError(error.message));
      } else {
        setAuthNotice("Account created! Sign in with your credentials.");
        setIsSignUp(false);
        setPasswordInput("");
      }
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) {
        setAuthNotice(readableAuthError(error.message));
      }
    }
    setIsAuthSubmitting(false);
  }

  async function signOut() {
    if (!supabase) return;
    await supabase.auth.signOut();
    setDraft("");
    setError(null);
  }

  async function submit(text: string) {
    const content = text.trim();
    if (!content || isStreaming) return;
    if (supabase && (!user || !accessToken)) {
      setError("Please sign in first.");
      return;
    }
    const isAuthenticated = Boolean(user && accessToken);

    const sessionId = await ensureSession();

    const userMessage: UiMessage = { id: crypto.randomUUID(), role: "user", content };
    const assistantMessageId = crypto.randomUUID();

    setMessages((current) => [
      ...current,
      userMessage,
      { id: assistantMessageId, role: "assistant", content: "Thinking...", status: "thinking" }
    ]);
    setDraft("");
    setError(null);
    setIsStreaming(true);

    const stream = streamChat({
      accessToken: isAuthenticated ? accessToken || undefined : undefined,
      message: content,
      conversationId: sessionId,
      history: messages
        .filter((item) => item.role === "user" || item.role === "assistant")
        .filter((item) => item.status !== "thinking")
        .map((item) => ({ role: item.role, content: item.content })),
      onEvent: (event) => {
        if (event.type === "thinking") {
          setMessages((current) =>
            current.map((item) =>
              item.id === assistantMessageId ? { ...item, content: "Thinking...", status: "thinking" } : item
            )
          );
          return;
        }

        if (event.type === "token") {
          setMessages((current) =>
            current.map((item) =>
              item.id === assistantMessageId
                ? { ...item, content: event.content || "Thinking...", status: "streaming" }
                : item
            )
          );
          return;
        }

        if (event.type === "done") {
          setMessages((current) =>
            current.map((item) =>
              item.id === assistantMessageId
                ? {
                    ...item,
                    content: event.response.answer,
                    response: event.response,
                    status: undefined
                  }
                : item
            )
          );
          setIsStreaming(false);
          if (isAuthenticated && accessToken) {
            void loadSessions(accessToken);
          }
          stream.close();
          return;
        }

        if (event.type === "error") {
          setError(reportAndSoftenError("chat:stream", event.message, "Streaming failed."));
          setDraft(content);
          setMessages((current) =>
            current.map((item) =>
              item.id === assistantMessageId
                ? {
                    ...item,
                    content: "I lost connection while streaming. Your draft is restored for retry.",
                    status: "failed"
                  }
                : item
            )
          );
          setIsStreaming(false);
          stream.close();
        }
      },
      onClose: () => {
        setIsStreaming(false);
      }
    });
  }

  if (isHydrating) {
    return <main className="grid h-[var(--app-height,100dvh)] place-items-center overflow-hidden text-sm text-muted-foreground">Loading...</main>;
  }

  if (supabase && !user) {
    return (
      <main className="relative grid h-[var(--app-height,100dvh)] place-items-center overflow-hidden bg-background px-4">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(122,136,255,0.28),transparent_50%),radial-gradient(ellipse_at_bottom_right,rgba(255,215,0,0.16),transparent_55%),linear-gradient(140deg,#060A20,#09103A_35%,#1A1B4A_68%,#100A2F)]" />
        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
          className="relative z-10 w-full max-w-md rounded-3xl border border-border/70 bg-card/70 p-7 shadow-halo backdrop-blur-xl"
        >
          <div className="flex items-center gap-2 text-accent">
            <Sparkles className="h-4 w-4" />
            <p className="text-xs uppercase tracking-[0.24em]">GitaGPT Mentor</p>
          </div>
          <h1 className="mt-3 text-3xl font-semibold text-foreground font-[var(--font-heading)]">Guidance begins when you ask honestly.</h1>
          <p className="mt-3 text-sm leading-7 text-muted-foreground">
            Continue your journey. Your past reflections, your questions, your growth—all in one place.
          </p>
          <Button className="mt-5 w-full bg-accent text-accent-foreground hover:bg-accent/90" onClick={signInWithGoogle}>
            Continue with Google
          </Button>
          <div className="mt-4 rounded-xl border border-border/70 bg-background/50 p-3">
            <label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{isSignUp ? "Create Account" : "Password Login"}</label>
            <input
              value={emailInput}
              onChange={(event) => setEmailInput(event.target.value)}
              placeholder="you@company.com"
              type="email"
              className="mt-2 w-full rounded-lg border border-border/70 bg-background px-3 py-2 text-sm outline-none ring-0 transition focus:border-accent"
            />
            <input
              value={passwordInput}
              onChange={(event) => setPasswordInput(event.target.value)}
              placeholder="••••••••"
              type="password"
              className="mt-2 w-full rounded-lg border border-border/70 bg-background px-3 py-2 text-sm outline-none ring-0 transition focus:border-accent"
              onKeyDown={(e) => e.key === "Enter" && handlePasswordAuth()}
            />
            <Button
              variant="outline"
              className="mt-3 w-full"
              onClick={handlePasswordAuth}
              disabled={isAuthSubmitting || !emailInput.trim() || !passwordInput.trim()}
            >
              {isSignUp ? "Create Account" : "Sign In"}
            </Button>
            <button
              onClick={() => {
                setIsSignUp(!isSignUp);
                setAuthNotice(null);
                setPasswordInput("");
              }}
              className="mt-3 w-full text-xs text-muted-foreground hover:text-accent transition"
            >
              {isSignUp ? "Already have an account? Sign in" : "Don't have an account? Sign up"}
            </button>
          </div>
          <p className="mt-3 min-h-5 text-xs text-muted-foreground">
            {authNotice || (isAuthSubmitting ? "Please wait..." : "")}
          </p>
        </motion.section>
      </main>
    );
  }

  const isAuthenticated = Boolean(user && accessToken);
  const initials = user?.email?.slice(0, 2).toUpperCase() || "GG";

  return (
    <main className="relative flex h-[var(--app-height,100dvh)] overflow-hidden bg-background">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(255,215,0,0.12),transparent_40%),radial-gradient(circle_at_90%_80%,rgba(114,89,255,0.2),transparent_38%),linear-gradient(135deg,#070D2A,#0B1D51_40%,#141B4A_72%,#090A1C)]" />

      <AnimatePresence initial={false}>
        {isAuthenticated && isSidebarOpen && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 300, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="group absolute inset-y-0 left-0 z-30 flex h-full w-[min(82vw,300px)] shrink-0 flex-col border-r border-border/70 bg-card/85 p-4 backdrop-blur-xl md:relative md:w-[300px]"
            style={{ overflow: "hidden" }}
            aria-label="Recent chats"
          >
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-[11px] uppercase tracking-[0.2em] text-accent">GitaGPT</p>
                <h1 className="text-lg font-semibold text-foreground">Mentor Sessions</h1>
              </div>
            </div>
            <Button className="mb-4 w-full bg-accent/90 text-accent-foreground hover:bg-accent/80 transition shadow-sm rounded-xl" onClick={createNewChat}>
              New Chat
            </Button>

            <ScrollArea className="min-h-0 flex-1">
              <div className="space-y-2 pb-2 pr-3">
                {sessions.map((session) => (
                  <div
                    key={session.id}
                    onClick={() => {
                      setActiveSessionId(session.id);
                      if (window.innerWidth < 768) {
                        setIsSidebarOpen(false);
                      }
                    }}
                    className={`group/item cursor-pointer w-full rounded-xl border px-3 py-3 text-left text-sm transition ${
                      activeSessionId === session.id
                        ? "border-accent/50 bg-accent/15 text-foreground"
                        : "border-border/60 bg-card/45 text-muted-foreground hover:border-accent/30 hover:text-foreground"
                    }`}
                  >
                    {editingSessionId === session.id ? (
                      <div className="flex items-center gap-2">
                        <input
                          autoFocus
                          className="flex-1 bg-background/50 border border-border/50 outline-none px-2 py-1 rounded text-foreground text-[13px] w-full"
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleRename(session.id);
                            if (e.key === "Escape") setEditingSessionId(null);
                          }}
                          onClick={(e) => e.stopPropagation()}
                        />
                        <button onClick={(e) => { e.stopPropagation(); handleRename(session.id); }} className="text-accent hover:text-accent/80 transition">
                          <Check className="h-4 w-4" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0 flex-1 line-clamp-1 font-medium select-none text-[13px]">{session.title}</div>
                        <div className="flex items-center gap-1.5 opacity-0 group-hover/item:opacity-100 transition-opacity duration-200">
                          <button 
                            type="button"
                            aria-label="Rename session"
                            onMouseDown={(e) => e.stopPropagation()}
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingSessionId(session.id);
                              setEditingTitle(session.title);
                            }}
                            className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                          >
                            <Edit2 className="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            aria-label="Delete session"
                            onMouseDown={(e) => e.stopPropagation()}
                            onClick={(e) => {
                              e.stopPropagation();
                              void handleDeleteSession(session.id);
                            }}
                            className="shrink-0 text-muted-foreground hover:text-rose-300 transition-colors"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    )}
                    <div className="mt-1.5 line-clamp-2 text-[11px] opacity-85 leading-relaxed">{session.summary || "No summary yet"}</div>
                  </div>
                ))}
              </div>
            </ScrollArea>

            <div className="mt-4 w-full shrink-0 rounded-xl border border-border/70 bg-background/45 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <Avatar>
                    <AvatarFallback>{initials}</AvatarFallback>
                  </Avatar>
                  <p className="truncate text-sm text-foreground">{user?.email}</p>
                </div>
                <Button size="icon" variant="ghost" onClick={signOut} aria-label="Sign out">
                  <LogOut className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {isAuthenticated && isSidebarOpen ? (
        <button
          type="button"
          aria-label="Close sidebar overlay"
          className="absolute inset-0 z-20 bg-[#020511]/55 backdrop-blur-[2px] md:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      ) : null}

      <section className="relative z-10 flex h-full min-h-0 flex-1 flex-col overflow-hidden" aria-label="GitaGPT chat">
        <header className="border-border/70 bg-transparent px-4 py-4 sm:px-6 z-20 shrink-0">
          <div className="flex items-center gap-4">
            {isAuthenticated && (
              <Button size="icon" variant="ghost" onClick={() => setIsSidebarOpen(!isSidebarOpen)} aria-label="Toggle sidebar" className="hover:bg-accent/15 hover:text-accent transition">
                <Menu className="h-5 w-5" />
              </Button>
            )}
            <div>
              <h2 className="text-xl font-semibold text-foreground sm:text-2xl font-[var(--font-heading)]">Divine Guidance</h2>
            </div>
          </div>
        </header>

        <div ref={viewportRef} onScroll={onScrollMessages} className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain">
          <AnimatePresence mode="wait">
            {messages.length === 0 ? (
              <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <EmptyState onPick={setDraft} prompts={starters} />
              </motion.div>
            ) : (
              <motion.div key="messages" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <MessageList messages={messages} />
                <div ref={endRef} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="composer-area shrink-0 border-t border-border/70 bg-[linear-gradient(180deg,rgba(10,16,39,0.78),rgba(12,18,46,0.96))] px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur-xl sm:px-6">
          <p aria-live="polite" className="min-h-5 text-xs text-rose-200">
            {error}
          </p>
          <ChatComposer
            value={draft}
            onChange={setDraft}
            onSubmit={submit}
            disabled={isStreaming}
            isStreaming={isStreaming}
          />
        </div>
      </section>
    </main>
  );
}

function toUiMessage(message: StoredMessage): UiMessage {
  return {
    id: String(message.id),
    role: message.role,
    content: message.content,
    response: message.response
  };
}

function readableAuthError(message: string): string {
  const normalized = message.toLowerCase();
  if (normalized.includes("unsupported provider") || normalized.includes("provider is not enabled")) {
    return "Google login is not enabled in Supabase. Enable Google under Authentication > Providers.";
  }
  if (normalized.includes("rate limit")) {
    return "Too many login emails sent. Wait a bit and try again.";
  }
  if (normalized.includes("user already") || normalized.includes("already registered")) {
    return "This email already exists. Use magic-link sign-in; do not delete the user.";
  }
  return message;
}

function reportAndSoftenError(scope: string, error: unknown, fallback: string): string {
  console.error(`[GitaGPT:${scope}]`, error);
  const raw =
    typeof error === "string"
      ? error
      : error instanceof Error
        ? error.message
        : fallback;
  return softenUiError(raw, fallback);
}

function softenUiError(rawMessage: string, fallback: string): string {
  const normalized = rawMessage.toLowerCase();

  if (
    normalized.includes("language model provider is unavailable") ||
    normalized.includes("all llm providers failed") ||
    (normalized.includes("forbidden") && normalized.includes("groq"))
  ) {
    return "LLM provider unavailable. Please try again shortly.";
  }

  if (normalized.includes("session persistence is unavailable") || normalized.includes("chat persistence is unavailable")) {
    return "Chat storage is temporarily unavailable. Please retry.";
  }

  if (normalized.includes("authentication required")) {
    return "Authentication required. Please sign in and retry.";
  }

  if (normalized.includes("streaming") || normalized.includes("connection")) {
    return "Streaming interrupted. Please retry.";
  }

  if (rawMessage.length > 160) {
    return fallback;
  }

  return rawMessage || fallback;
}
