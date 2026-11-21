import { History, MessageSquare, Plus } from "lucide-react";
import { useChat } from "../state/chat";
import { useSession } from "../state/session";
import { useUI } from "../state/ui";
import { Popover } from "./Popover";
import { Spinner } from "./common";

export function ChatHistory({ onSelect }: { onSelect?: () => void }) {
  const { t, state } = useSession();
  const { setTab, setDraft } = useUI();
  const { history, loadingConversation, openConversation, newConversation } = useChat();

  function selectChat(id?: string) {
    setDraft("");
    setTab("ask");
    if (id) openConversation(id);
    else newConversation();
    onSelect?.();
  }

  return (
    <section className="chat-history" aria-label={t("chatHistory")}>
      <div className="chat-history-header">
        <h2>{t("chatHistory")}</h2>
        <button type="button" className="icon-btn" aria-label={t("newConversation")} title={t("newConversation")}
          onClick={() => selectChat()}>
          <Plus size={18} aria-hidden="true" />
        </button>
      </div>
      {history.loading && !history.data && <Spinner label={t("loading")} />}
      {history.error && (
        <div className="small error-text" role="alert">
          {history.error} <button type="button" className="link-btn" onClick={history.reload}>{t("retry")}</button>
        </div>
      )}
      {history.data?.length === 0 && <p className="small muted">{t("noSavedChats")}</p>}
      <div className="chat-history-list">
        {history.data?.map(({ conversation_id: id, title }) => {
          const current = state.conversationId === id;
          const name = title?.trim() || t("untitledChat");
          return (
            <button key={id} type="button" className={`chat-history-item ${current ? "is-active" : ""}`}
              title={name} aria-current={current || undefined} aria-busy={loadingConversation === id}
              onClick={() => selectChat(id)}>
              <MessageSquare size={15} aria-hidden="true" />
              <span dir="auto">{name}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export function MobileChatHistory() {
  const { t } = useSession();
  return (
    <div className="chat-history-mobile">
      <Popover label={t("chatHistory")} align="start" trigger={(props) => (
        <button type="button" className="btn btn--ghost btn--sm" {...props}>
          <History size={17} aria-hidden="true" /> {t("chatHistory")}
        </button>
      )}>
        {(close) => <ChatHistory onSelect={close} />}
      </Popover>
    </div>
  );
}
