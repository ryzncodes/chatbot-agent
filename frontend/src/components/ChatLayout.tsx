import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { sendChatMessage } from "../services/api";
import { useChatStore } from "../state/chatStore";

import styles from "./ChatLayout.module.css";

const QUICK_COMMANDS = ["/calc", "/products", "/outlets", "/reset"];

function ChatLayout() {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [input, setInput] = useState("");

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

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      const trimmed = input.trim();
      if (!trimmed) return;

      setStatus("loading");
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
        });
        setStatus("idle");

        if (response.action === "finish") {
          reset();
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setStatus("error", message);
      }
    },
    [appendMessage, conversationId, input, recordPlannerEvent, reset, setStatus]
  );

  const statusMessage = useMemo(() => {
    if (status === "loading") return "Thinking...";
    if (status === "error") return error ?? "Something went wrong";
    return "Online";
  }, [status, error]);

  const handleQuickCommand = (command: string) => {
    setInput((current) => `${command} ${current}`.trim() + " ");
    textareaRef.current?.focus();
  };

  const sortedSlots = Object.entries(slots);

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

        <div className={styles.messageList}>
          {messages.length === 0 && <p>Start the conversation by asking about products, outlets, or calculations.</p>}
          {messages.map((msg) => (
            <ChatBubble key={`${msg.conversation_id}-${msg.content}-${msg.role}-${Math.random()}`} message={msg} />
          ))}
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
          <div className={styles.statusBar}>
            <span className={status === "error" ? "error" : "loading"}>{statusMessage}</span>
          </div>
        </form>
      </section>

      <aside className={styles.panel}>
        <header className={styles.timelineHeader}>
          <h2 className={styles.title}>Planner Timeline</h2>
          <span className={styles.badge}>{timeline.length} events</span>
        </header>

        <div className={styles.timelineList}>
          {timeline.length === 0 && <p>No planner decisions yet.</p>}
          {timeline.map((event) => (
            <div
              key={event.timestamp}
              className={`${styles.timelineItem} ${event.toolSuccess ? "success" : "error"}`}
            >
              <div className={styles.timelineMeta}>
                {new Date(event.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                &nbsp;· Intent: <strong>{event.intent}</strong>
              </div>
              <div>
                <strong>Action:</strong> {event.action}
              </div>
              <div>{event.message}</div>
            </div>
          ))}
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
