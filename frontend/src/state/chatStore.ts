import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { ChatMessage, ChatResponse } from "../services/api";

type PlannerTimelineEvent = {
  timestamp: string;
  intent: string;
  action: string;
  message: string;
  toolSuccess: boolean;
  tool: string | null;
  requiredSlots: Record<string, boolean>;
};

type ChatState = {
  conversationId: string;
  messages: ChatMessage[];
  slots: Record<string, string>;
  timeline: PlannerTimelineEvent[];
  lastDecision: PlannerTimelineEvent | null;
  status: "idle" | "loading" | "error";
  error?: string;
  setConversationId: (id: string) => void;
  appendMessage: (message: ChatMessage) => void;
  recordPlannerEvent: (response: ChatResponse) => void;
  setStatus: (status: ChatState["status"], error?: string) => void;
  reset: () => void;
};

function createTimelineEvent(response: ChatResponse): PlannerTimelineEvent {
  const timestamp = new Date().toISOString();
  const tool = response.action.startsWith("call_") ? response.action : null;
  return {
    timestamp,
    intent: response.intent,
    action: response.action,
    message: response.message,
    toolSuccess: response.tool_success,
    tool,
    requiredSlots: response.required_slots,
  };
}

function defaultConversationId() {
  return `conv-${crypto.randomUUID()}`;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      conversationId: defaultConversationId(),
      messages: [],
      slots: {},
      timeline: [],
      lastDecision: null,
      status: "idle",
      setConversationId: (id) => set({ conversationId: id }),
      appendMessage: (message) =>
        set((state) => {
          const timestamped = message.created_at
            ? message
            : { ...message, created_at: new Date().toISOString() };
          return { messages: [...state.messages, timestamped] };
        }),
      recordPlannerEvent: (response) =>
        set((state) => {
          const event = createTimelineEvent(response);
          return {
            timeline: [...state.timeline, event],
            slots: response.slots,
            lastDecision: event,
          };
        }),
      setStatus: (status, error) => set({ status, error }),
      reset: () =>
        set({
          conversationId: defaultConversationId(),
          messages: [],
          slots: {},
          timeline: [],
          lastDecision: null,
          status: "idle",
          error: undefined,
        }),
    }),
    { name: "zus-chat-state" }
  )
);
