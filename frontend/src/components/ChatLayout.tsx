import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ChatMessage } from "../services/api";
import { fetchMetrics, sendChatMessage } from "../services/api";
import { useChatStore } from "../state/chatStore";

import styles from "./ChatLayout.module.css";
import AutocompleteHints from "./AutocompleteHints";

const QUICK_COMMANDS = ["/calc", "/products", "/outlets", "/reset"];

type ToolAvailability = "ok" | "degraded";

function ChatLayout() {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const scrollAnchorRef = useRef<HTMLDivElement | null>(null);
  const hasAutoScrolledRef = useRef(false);
  const [input, setInput] = useState("");
  const [toolStatus, setToolStatus] = useState<ToolAvailability>("ok");
  const [lastTool, setLastTool] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<{ total?: number } | null>(null);

  const {
    conversationId,
    messages,
    timeline,
    slots,
    status,
    error,
    appendMessage,
    recordPlannerEvent,
    setStatus,
    reset,
  } = useChatStore();
  const [isTyping, setIsTyping] = useState(false);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const isNearBottom = useCallback(() => {
    const list = messageListRef.current;
    if (!list) return true;
    const threshold = 56;
    return list.scrollHeight - list.scrollTop - list.clientHeight <= threshold;
  }, []);

  useEffect(() => {
    if (!messageListRef.current) return;
    if (!isNearBottom() && hasAutoScrolledRef.current) return;
    const behavior = hasAutoScrolledRef.current ? "smooth" : "auto";
    if (scrollAnchorRef.current) {
      scrollAnchorRef.current.scrollIntoView({ behavior, block: "end" });
    } else {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
    }
    hasAutoScrolledRef.current = true;
  }, [messages, isTyping, isNearBottom]);

  const handleSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      const trimmed = input.trim();
      if (!trimmed) return;

      setStatus("loading");
      setIsTyping(true);
      const outgoing = {
        conversation_id: conversationId,
        role: "user" as const,
        content: trimmed,
      };
      appendMessage(outgoing);
      setInput("");

      try {
        const response = await sendChatMessage(outgoing);
        recordPlannerEvent(response);
        appendMessage({
          conversation_id: conversationId,
          role: "assistant",
          content: response.message,
          created_at: new Date().toISOString(),
        });
        setStatus("idle");
        setIsTyping(false);

        if (response.action === "finish") {
          reset();
        }
        setLastTool(response.action.startsWith("call_") ? response.action : null);
        setToolStatus(response.tool_success ? "ok" : "degraded");
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setStatus("error", message);
        setToolStatus("degraded");
        setIsTyping(false);
      }
    },
    [appendMessage, conversationId, input, recordPlannerEvent, reset, setStatus]
  );

  const statusMessage = useMemo(() => {
    if (status === "loading") return "Thinking...";
    if (status === "error") return error ?? "Something went wrong";
    return "Online";
  }, [status, error]);

  const threads = useMemo<ChatMessage[][]>(() => {
    const grouped: ChatMessage[][] = [];
    let current: ChatMessage[] = [];
    messages.forEach((msg) => {
      current.push(msg);
      if (msg.role === "assistant") {
        grouped.push(current);
        current = [];
      }
    });
    if (current.length) {
      grouped.push(current);
    }
    return grouped;
  }, [messages]);

  useEffect(() => {
    const poll = async () => {
      try {
        const data = (await fetchMetrics()) as { total_requests?: number };
        setMetrics({ total: data.total_requests ?? 0 });
      } catch (err) {
        console.warn("Failed to fetch metrics", err);
      }
    };
    poll();
    const interval = setInterval(poll, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleQuickCommand = (command: string) => {
    if (command === "/reset") {
      reset();
      setInput("");
      return;
    }
    if (command === "/calc") {
      setInput(() => `${command} 1 + 2`.trim() + " ");
    } else if (command === "/products") {
      setInput(() => `${command} What tumblers do you have?`.trim() + " ");
    } else if (command === "/outlets") {
      setInput(() => `${command} What are the hours for SS2?`.trim() + " ");
    } else {
      setInput((current) => `${command} ${current}`.trim() + " ");
    }
    textareaRef.current?.focus();
  };

  const sortedSlots = useMemo(
    () => Object.entries(slots).sort(([a], [b]) => a.localeCompare(b)),
    [slots]
  );

  return (
    <div className={styles.layout}>
      <aside className={`${styles.panel}`}>
        <header className={styles.slotHeader}>
          <h2 className={styles.title}>Memory</h2>
          <span className={styles.badge}>{sortedSlots.length} slots</span>
        </header>

        <div className={styles.slotList}>
          {sortedSlots.length === 0 && <p>No slots captured yet.</p>}
          {sortedSlots.map(([key, value]) => (
            <div key={key} className={styles.slotCard}>
              <div className={styles.slotLabel}>{key.replace(/_/g, " ")}</div>
              <div className={styles.slotValue}>{value}</div>
            </div>
          ))}
        </div>
      </aside>

      <section className={`${styles.panel} ${styles.chatPanel}`}>
        <header>
          <h1 className={styles.title}>ZUS AI Assistant</h1>
        </header>

        <div ref={messageListRef} className={styles.messageList}>
          {threads.length === 0 && <p>Start the conversation by asking about products, outlets, or calculations.</p>}
          {threads.map((threadMessages, index) => {
            const turnNumber = index + 1;
            const meta = timeline[index];
            return (
              <div key={`thread-${index}`} className={styles.thread}>
                <div className={styles.threadHeader}>
                  <span>Turn {turnNumber}</span>
                  {meta && <span className={styles.intentBadge}>{meta.intent}</span>}
                </div>
                <div className={styles.threadMessages}>
                  {threadMessages.map((msg, msgIndex) => (
                    <ChatBubble key={`${msg.conversation_id}-${msg.created_at ?? msgIndex}`} message={msg} />
                  ))}
                </div>
              </div>
            );
          })}
          {isTyping && (
            <div className={`${styles.bubble} ${styles.bubbleBot}`}>
              <div className={styles.typingIndicator}>
                <span></span>
                <span></span>
                <span></span>
              </div>
              <div className={styles.bubbleMeta}>Assistant is typing…</div>
            </div>
          )}
          <div ref={scrollAnchorRef} aria-hidden="true" />
        </div>

        <form className={styles.composer} onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            className={styles.textarea}
            placeholder="Type your message..."
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleSubmit(event);
              }
            }}
          />

          <div className={styles.controls}>
            <div className={styles.quickCommands}>
              {QUICK_COMMANDS.map((command) => (
                <button
                  type="button"
                  key={command}
                  className={styles.chip}
                  onClick={() => handleQuickCommand(command)}
                >
                  {command}
                </button>
              ))}
            </div>
            <button className={styles.sendButton} type="submit" disabled={status === "loading"}>
              Send
            </button>
          </div>
          <AutocompleteHints input={input} commands={QUICK_COMMANDS} />
          <div className={styles.statusBar}>
            <span
              className={`${styles.statusDot} ${status === "error" ? styles.statusError : status === "loading" ? styles.statusLoading : styles.statusOk}`}
            ></span>
            <span className={styles.statusText}>{statusMessage}</span>
            {lastTool && (
              <span
                className={`${styles.toolIndicator} ${
                  toolStatus === "ok" ? styles.toolIndicatorSuccess : styles.toolIndicatorError
                }`}
              >
                ⚙️ {lastTool.replace("call_", "")}
              </span>
            )}
            {metrics?.total !== undefined && <span className={styles.statusText}>· {metrics.total} turns</span>}
          </div>
          {status === "error" && error && <div className={styles.errorBanner}>⚠️ {error}</div>}
        </form>
      </section>

      <aside className={styles.panel}>
        <header className={styles.timelineHeader}>
          <h2 className={styles.title}>Planner Timeline</h2>
          <span className={styles.badge}>{timeline.length} events</span>
        </header>

        <div className={styles.timelineList}>
          {timeline.length === 0 && <p>No planner decisions yet.</p>}
          {timeline.map((event) => {
            const missingSlots = Object.entries(event.requiredSlots)
              .filter(([, satisfied]) => !satisfied)
              .map(([slot]) => slot.replace(/_/g, " "));
            return (
              <div
                key={event.timestamp}
                className={`${styles.timelineItem} ${
                  event.toolSuccess ? styles.timelineItemSuccess : styles.timelineItemError
                }`}
              >
                <div className={styles.timelineMeta}>
                  {new Date(event.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                  &nbsp;· Intent: <strong>{event.intent}</strong>
                </div>
                <div>
                  <strong>Action:</strong> {event.action}
                </div>
                <div>{event.message}</div>
                {missingSlots.length > 0 && (
                  <div>
                    <strong>Missing slots:</strong> {missingSlots.join(", ")}
                  </div>
                )}
                {event.tool && (
                  <div
                    className={`${styles.toolIndicator} ${
                      event.toolSuccess ? styles.toolIndicatorSuccess : styles.toolIndicatorError
                    }`}
                  >
                    Tool: {event.tool.replace("call_", "")}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </aside>
    </div>
  );
}

function ChatBubble({
  message,
}: {
  message: { conversation_id: string; role: "user" | "assistant"; content: string; created_at?: string };
}) {
  const isUser = message.role === "user";
  const timestamp = message.created_at
    ? new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className={`${styles.bubble} ${isUser ? styles.bubbleUser : styles.bubbleBot}`}>
      <div>{message.content}</div>
      <div className={styles.bubbleMeta}>{isUser ? "You" : "Assistant"} · {timestamp}</div>
    </div>
  );
}

export default ChatLayout;
