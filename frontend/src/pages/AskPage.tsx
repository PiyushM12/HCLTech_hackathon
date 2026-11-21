import { ChatView } from "../components/ChatView";
import { Composer } from "../components/Composer";
import { MobileChatHistory } from "../components/ChatHistory";
import { ErrorNotice, LoadingBlock } from "../components/common";
import { useChat } from "../state/chat";
import { useSession } from "../state/session";

export function AskPage() {
  const { state, t } = useSession();
  const { loadingConversation, conversationError, openConversation } = useChat();
  return (
    <div className="chat">
      <MobileChatHistory />
      {conversationError && <ErrorNotice error={conversationError.message} onRetry={() => openConversation(conversationError.id)} />}
      {loadingConversation ? (
        <LoadingBlock label={t("loading")} />
      ) : (
        <ChatView key={`view-${state.conversationVersion}`} />
      )}
      <Composer key={`composer-${state.conversationVersion}`} />
    </div>
  );
}
