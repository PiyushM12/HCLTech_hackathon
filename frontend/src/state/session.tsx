// Keep the active chat in memory and restore the account from the server cookie.
import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useState, type Dispatch, type ReactNode } from "react";
import { api } from "../api";
import type { Account, AccountRole, AnswerType, ChatAnswer, EligibilityAttributes, Lang, PendingAction } from "../types";
import { makeT, type Translate, type UiLanguage } from "../i18n";
import { loadJSON, saveJSON } from "../lib/storage";

export type ActionPhase = "pending" | "confirming" | "cancelling" | "executed" | "cancelled" | "error";
export type ActionErrorKind = "already" | "expired" | "forbidden" | "notfound" | "other";

export interface ActionState {
  phase: ActionPhase;
  result?: Record<string, unknown>;
  verified?: boolean;
  error?: string;
  errorKind?: ActionErrorKind;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
  answerType?: AnswerType;
  language?: Lang;
  traceId?: string;
  response?: ChatAnswer;
  /** Lifecycle of response.pending_action, if any. */
  actionState?: ActionState;
  /** For the assistant message created from a confirm call. */
  actionResult?: { action: PendingAction; result: Record<string, unknown>; verified: boolean };
}

export interface SessionState {
  account: Account | null;
  language: UiLanguage;
  /** null = today */
  asOfDate: string | null;
  conversationId: string | null;
  conversationVersion: number;
  messages: ChatMessage[];
  eligibilityAttributes: EligibilityAttributes | null;
}

type Action =
  | { type: "setAccount"; account: Account | null }
  | { type: "setLanguage"; language: UiLanguage }
  | { type: "setAsOfDate"; date: string | null }
  | { type: "newConversation" }
  | { type: "restoreConversation"; id: string; messages: ChatMessage[] }
  | { type: "setEligibilityAttributes"; attributes: EligibilityAttributes | null; account: Account | null }
  | { type: "addMessage"; message: ChatMessage }
  | { type: "setConversationId"; id: string }
  | { type: "updateAction"; messageId: string; patch: Partial<ActionState>; reply?: ChatMessage };

const STORAGE_KEY = "schemesathi.session.v1";

const initialState: SessionState = {
  account: null,
  language: "auto",
  asOfDate: null,
  conversationId: null,
  conversationVersion: 0,
  messages: [],
  eligibilityAttributes: null,
};

function loadInitial(): SessionState {
  const saved = loadJSON<Partial<Pick<SessionState, "language" | "asOfDate">>>(STORAGE_KEY);
  if (!saved || typeof saved !== "object") return initialState;
  return {
    ...initialState,
    language: (["auto", "hi", "en", "kn", "ta"] as const).includes(saved.language as UiLanguage)
      ? (saved.language as UiLanguage)
      : "auto",
    asOfDate: typeof saved.asOfDate === "string" ? saved.asOfDate : null,
  };
}

function reducer(state: SessionState, action: Action): SessionState {
  switch (action.type) {
    case "setAccount":
      return { ...state, account: action.account, conversationId: null, messages: [], eligibilityAttributes: null };
    case "setLanguage":
      return { ...state, language: action.language };
    case "setAsOfDate":
      return { ...state, asOfDate: action.date };
    case "newConversation":
      return { ...state, conversationId: null, messages: [], conversationVersion: state.conversationVersion + 1 };
    case "restoreConversation":
      return { ...state, conversationId: action.id, messages: action.messages, conversationVersion: state.conversationVersion + 1 };
    case "setEligibilityAttributes":
      return state.account === action.account ? { ...state, eligibilityAttributes: action.attributes } : state;
    case "addMessage":
      return { ...state, messages: [...state.messages, action.message] };
    case "setConversationId":
      return { ...state, conversationId: action.id };
    case "updateAction": {
      const index = state.messages.findIndex((message) => message.id === action.messageId);
      if (index < 0) return state;
      const messages = state.messages.slice();
      const message = messages[index];
      messages[index] = { ...message, actionState: { ...(message.actionState ?? { phase: "pending" }), ...action.patch } };
      if (action.reply) messages.push(action.reply);
      return { ...state, messages };
    }
    default:
      return state;
  }
}

interface SessionContextValue {
  state: SessionState;
  dispatch: Dispatch<Action>;
  t: Translate;
  checkingAccount: boolean;
  signIn: (role: AccountRole, username: string, password: string) => Promise<void>;
  register: (username: string, password: string, consent: boolean) => Promise<void>;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, loadInitial);
  const [checkingAccount, setCheckingAccount] = useState(true);

  useEffect(() => {
    let active = true;
    api.me().then(({ account }) => {
      if (active) dispatch({ type: "setAccount", account });
    }).catch(() => {
      if (active) dispatch({ type: "setAccount", account: null });
    }).finally(() => {
      if (active) setCheckingAccount(false);
    });
    return () => { active = false; };
  }, []);

  const signIn = useCallback(async (role: AccountRole, username: string, password: string) => {
    const { account } = await api.login(role, username, password);
    dispatch({ type: "setAccount", account });
  }, []);

  const register = useCallback(async (username: string, password: string, consent: boolean) => {
    const { account } = await api.register(username, password, consent);
    dispatch({ type: "setAccount", account });
  }, []);

  const signOut = useCallback(async () => {
    await api.logout();
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    dispatch({ type: "setAccount", account: null });
  }, []);

  useEffect(() => {
    saveJSON(STORAGE_KEY, { language: state.language, asOfDate: state.asOfDate });
  }, [state.language, state.asOfDate]);

  useEffect(() => {
    const lang = state.language === "auto" ? "en" : state.language;
    document.documentElement.lang = lang;
  }, [state.language]);

  const value = useMemo<SessionContextValue>(
    () => ({ state, dispatch, t: makeT(state.language), checkingAccount, signIn, register, signOut }),
    [state, checkingAccount, signIn, register, signOut],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}

export function useT(): Translate {
  return useSession().t;
}

