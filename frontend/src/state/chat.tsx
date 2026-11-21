// Chat runtime: sending messages, retrying, and confirming / cancelling proposed actions.
// Lives above the pages so an answer still lands if the user switches tabs while waiting.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, errorMessage } from "../api";
import { uid } from "../lib/format";
import { useAsync, type AsyncState } from "../lib/useAsync";
import type { ConversationMessage, ConversationSummary, ReplyLang } from "../types";
import { useSession, type ActionErrorKind, type ActionState, type ChatMessage } from "./session";

interface ChatError {
  message: string;
  /** The text to resend on retry. */
  text: string;
  language?: ReplyLang;
}

interface ChatContextValue {
  pending: boolean;
  error: ChatError | null;
  /** `language` overrides the reply language for this one turn (used by quick replies). */
  send: (text: string, opts?: { language?: ReplyLang }) => void;
  retry: () => void;
  dismissError: () => void;
  confirmAction: (messageId: string) => void;
  cancelAction: (messageId: string) => void;
  newConversation: () => void;
  openConversation: (id: string) => void;
  history: AsyncState<ConversationSummary[]>;
  loadingConversation: string | null;
  conversationError: { id: string; message: string } | null;
}

const ChatContext = createContext<ChatContextValue | null>(null);

function classifyActionError(err: unknown): ActionErrorKind {
  if (!(err instanceof ApiError)) return "other";
  if (err.status === 409) return "already";
  if (err.status === 410) return "expired";
  if (err.status === 403) return "forbidden";
  if (err.status === 404) return "notfound";
  return "other";
}

function actionErrorPatch(err: unknown): Partial<ActionState> {
  const kind = classifyActionError(err);
  const terminal = kind === "already" || kind === "expired" || kind === "notfound";
  return { phase: terminal ? "error" : "pending", errorKind: kind, error: errorMessage(err) };
}

function restoredMessage(message: ConversationMessage): ChatMessage[] {
  if (message.role !== "user" && message.role !== "assistant") return [];
  const action = message.response?.pending_action;
  const status = action?.status;
  const actionState: ActionState | undefined = action ? {
    phase: status === "executed" ? "executed" : status === "cancelled" ? "cancelled"
      : status === "expired" ? "error" : "pending",
    errorKind: status === "expired" ? "expired" : undefined,
    result: message.action_result?.result,
    verified: message.action_result?.verified,
  } : undefined;
  return [{
    id: message.trace_id ? `a-${message.trace_id}` : `saved-${message.message_id}`,
    role: message.role,
    text: message.text,
    createdAt: `${message.created_at.replace(" ", "T")}Z`,
    answerType: message.answer_type ?? undefined,
    language: message.language ?? undefined,
    traceId: message.trace_id ?? undefined,
    response: message.response,
    actionState,
  }];
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const { state, dispatch } = useSession();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ChatError | null>(null);
  const [loadingConversation, setLoadingConversation] = useState<string | null>(null);
  const [conversationError, setConversationError] = useState<ChatContextValue["conversationError"]>(null);
  const history = useAsync(api.conversations, []);
  const reloadHistory = history.reload;
  const stateRef = useRef(state);
  stateRef.current = state;
  const abortRef = useRef<AbortController | null>(null);
  const loadRef = useRef<{ id: string; controller: AbortController } | null>(null);
  const inFlight = useRef(new Set<string>());
  const [sendingIds, setSendingIds] = useState<string[]>([]);
  const activeRef = useRef(true);
  const pendingRef = useRef(false);
  const visibleConversationId = useCallback(() => loadRef.current?.id ?? stateRef.current.conversationId, []);

  const detachPending = useCallback(() => {
    // Let a submitted turn finish and appear in history if the user switches chats.
    abortRef.current = null;
    pendingRef.current = false;
    setPending(false);
    setError(null);
  }, []);

  useEffect(() => {
    activeRef.current = true;
    return () => {
      activeRef.current = false;
      abortRef.current?.abort();
      loadRef.current?.controller.abort();
    };
  }, []);

  const openConversation = useCallback(async (id: string, refresh = false) => {
    loadRef.current?.controller.abort();
    loadRef.current = null;
    setLoadingConversation(null);
    setConversationError(null);
    if (!refresh && id === stateRef.current.conversationId) return;
    detachPending();
    const controller = new AbortController();
    loadRef.current = { id, controller };
    setLoadingConversation(id);
    try {
      const saved = await api.conversation(id, controller.signal);
      if (!controller.signal.aborted) {
        dispatch({ type: "restoreConversation", id: saved.conversation_id, messages: saved.messages.flatMap(restoredMessage) });
      }
    } catch (err) {
      if (!controller.signal.aborted) setConversationError({ id, message: errorMessage(err) });
    } finally {
      if (loadRef.current?.controller === controller) {
        loadRef.current = null;
        setLoadingConversation(null);
      }
    }
  }, [detachPending, dispatch]);

  const ask = useCallback(
    async (text: string, addUserMessage: boolean, languageOverride?: ReplyLang) => {
      const trimmed = text.trim();
      if (!trimmed || pendingRef.current || loadRef.current) return;
      const s = stateRef.current;
      const id = s.conversationId;
      if (id && inFlight.current.has(id)) return;
      if (id) {
        inFlight.current.add(id);
        setSendingIds([...inFlight.current]);
      }
      if (addUserMessage) {
        dispatch({
          type: "addMessage",
          message: { id: uid("u"), role: "user", text: trimmed, createdAt: new Date().toISOString() },
        });
      }
      setError(null);
      setPending(true);
      pendingRef.current = true;
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const res = await api.ask(
          {
            message: trimmed,
            conversation_id: s.conversationId ?? undefined,
            channel: "web",
            language: s.language === "auto" ? languageOverride : s.language,
            as_of_date: s.asOfDate ?? undefined,
          },
          controller.signal,
        );
        if (activeRef.current) reloadHistory();
        if (controller.signal.aborted || stateRef.current.account !== s.account || !activeRef.current) return;
        if (abortRef.current !== controller) {
          const visibleId = visibleConversationId();
          if (res.conversation_id === visibleId) await openConversation(visibleId, true);
          return;
        }
        dispatch({ type: "setConversationId", id: res.conversation_id });
        const msg: ChatMessage = {
          id: `a-${res.trace_id}`,
          role: "assistant",
          text: res.answer,
          createdAt: new Date().toISOString(),
          answerType: res.answer_type,
          language: res.language,
          traceId: res.trace_id,
          response: res,
        };
        if (res.pending_action) {
          const st = res.pending_action.status;
          msg.actionState = { phase: st === "executed" ? "executed" : st === "cancelled" ? "cancelled" : "pending" };
        }
        dispatch({ type: "addMessage", message: msg });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (abortRef.current !== controller || controller.signal.aborted) return;
        setError({ message: errorMessage(err), text: trimmed, language: languageOverride });
      } finally {
        if (id) {
          inFlight.current.delete(id);
          if (activeRef.current) setSendingIds([...inFlight.current]);
        }
        if (abortRef.current === controller) {
          abortRef.current = null;
          pendingRef.current = false;
          setPending(false);
        }
      }
    },
    [dispatch, openConversation, reloadHistory, visibleConversationId],
  );

  const findMessage = (id: string) => stateRef.current.messages.find((m) => m.id === id);

  const confirmAction = useCallback(
    async (messageId: string) => {
      const msg = findMessage(messageId);
      const action = msg?.response?.pending_action;
      if (!msg || !action) return;
      dispatch({ type: "updateAction", messageId, patch: { phase: "confirming", error: undefined, errorKind: undefined } });
      try {
        const res = await api.confirmAction(action.action_id);
        if (!activeRef.current) return;
        reloadHistory();
        dispatch({
          type: "updateAction",
          messageId,
          patch: { phase: "executed", result: res.result, verified: res.verified },
          reply: {
            id: `a-${res.trace_id}`,
            role: "assistant",
            text: res.answer,
            createdAt: new Date().toISOString(),
            answerType: res.answer_type ?? "action_completed",
            language: res.language,
            traceId: res.trace_id,
            actionResult: { action: res.action, result: res.result ?? {}, verified: !!res.verified },
          },
        });
      } catch (err) {
        dispatch({ type: "updateAction", messageId, patch: actionErrorPatch(err) });
      }
    },
    [dispatch, reloadHistory],
  );

  const cancelAction = useCallback(
    async (messageId: string) => {
      const msg = findMessage(messageId);
      const action = msg?.response?.pending_action;
      if (!msg || !action) return;
      dispatch({ type: "updateAction", messageId, patch: { phase: "cancelling", error: undefined, errorKind: undefined } });
      try {
        const res = await api.cancelAction(action.action_id);
        if (!activeRef.current) return;
        reloadHistory();
        dispatch({
          type: "updateAction",
          messageId,
          patch: { phase: "cancelled" },
          reply: res.answer ? {
            id: `a-${res.trace_id}`,
            role: "assistant",
            text: res.answer,
            createdAt: new Date().toISOString(),
            answerType: res.answer_type ?? "answered",
            language: res.language,
            traceId: res.trace_id,
          } : undefined,
        });
      } catch (err) {
        dispatch({ type: "updateAction", messageId, patch: actionErrorPatch(err) });
      }
    },
    [dispatch, reloadHistory],
  );

  const value = useMemo<ChatContextValue>(
    () => ({
      pending: pending || (!!state.conversationId && sendingIds.includes(state.conversationId)),
      error,
      history,
      loadingConversation,
      conversationError,
      openConversation,
      send: (text, opts) => void ask(text, true, opts?.language),
      retry: () => {
        if (error) void ask(error.text, false, error.language);
      },
      dismissError: () => setError(null),
      confirmAction: (id) => void confirmAction(id),
      cancelAction: (id) => void cancelAction(id),
      newConversation: () => {
        loadRef.current?.controller.abort();
        loadRef.current = null;
        setLoadingConversation(null);
        setConversationError(null);
        detachPending();
        dispatch({ type: "newConversation" });
      },
    }),
    [pending, state.conversationId, sendingIds, error, history, loadingConversation, conversationError,
      openConversation, ask, confirmAction, cancelAction, dispatch, detachPending],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used inside ChatProvider");
  return ctx;
}
