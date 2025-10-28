import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { ChatMessage, ChatResponse } from "../services/api";

type PlannerTimelineEvent = {
  timestamp: string;
  intent: string;
  action: string;
  message: string;
  toolSuccess: boolean;
};

type ChatState = {
  conversationId: string;
  messages: ChatMessage[];
  slots: Record<string, string>;
  timeline: PlannerTimelineEvent[];
  status: "idle" | "loading" | "error";
  error?: string;
  setConversationId: (id: string) => void;
  appendMessage: (message: ChatMessage) => void;
  recordPlannerEvent: (response: ChatResponse) => void;
  setStatus: (status: ChatState["status"], error?: string) => void;
  reset: () => void;
};

function defaultConversationId() {
  return `conv-${crypto.randomUUID()}`;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      conversationId: defaultConversationId(),
      messages: [],
      slots: {},
      timeline: [],
      status: "idle",
      setConversationId: (id) => set({ conversationId: id }),
      appendMessage: (message) => set({ messages: [...get().messages, message] }),
      recordPlannerEvent: (response) =>
        set((state) => ({
          timeline: [
            ...state.timeline,
            {
              timestamp: new Date().toISOString(),
              intent: response.intent,
              action: response.action,
              message: response.message,
              toolSuccess: response.tool_success,
            },
          ],
          slots: {
            ...state.slots,
            ...Object.fromEntries(
              Object.entries(response.required_slots).filter(([, satisfied]) => satisfied)
            ),
          },
        })),
      setStatus: (status, error) => set({ status, error }),
      reset: () =>
        set({
          conversationId: defaultConversationId(),
          messages: [],
          slots: {},
          timeline: [],
          status: "idle",
          error: undefined,
        }),
    }),
    { name: "zus-chat-state" }
  )
);
