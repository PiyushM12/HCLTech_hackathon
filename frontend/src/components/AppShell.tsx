import type { ReactNode } from "react";
import { ClipboardCheck, LayoutGrid, Library, MessagesSquare, type LucideIcon } from "lucide-react";
import type { I18nKey } from "../i18n";
import { useSession } from "../state/session";
import { useChat } from "../state/chat";
import { useUI, type Tab } from "../state/ui";
import { TopBar } from "./TopBar";
import { DrawerHost } from "./DrawerHost";
import { ChatHistory } from "./ChatHistory";

const NAV: { tab: Tab; icon: LucideIcon; label: I18nKey; short?: I18nKey }[] = [
  { tab: "ask", icon: MessagesSquare, label: "navAsk", short: "navAskShort" },
  { tab: "eligibility", icon: ClipboardCheck, label: "navEligibility", short: "navEligibilityShort" },
  { tab: "schemes", icon: LayoutGrid, label: "navSchemes", short: "navSchemesShort" },
  { tab: "sources", icon: Library, label: "navSources", short: "navSourcesShort" },
];

function Nav() {
  const { t } = useSession();
  const { tab, setTab } = useUI();
  const { pending } = useChat();
  return (
    <aside className="nav">
      <nav aria-label={t("mainNav")}>
        <ul>
          {NAV.map(({ tab: id, icon: Icon, label, short }) => (
            <li key={id}>
              <a
                href={`#/${id}`}
                className={`nav-item ${tab === id ? "is-active" : ""}`}
                aria-current={tab === id ? "page" : undefined}
                onClick={(e) => {
                  e.preventDefault();
                  setTab(id);
                }}
              >
                <span className="nav-icon">
                  <Icon size={20} aria-hidden="true" />
                  {id === "ask" && pending && tab !== "ask" && <span className="nav-dot" aria-hidden="true" />}
                </span>
                <span className="nav-label nav-label--long">{t(label)}</span>
                <span className="nav-label nav-label--short">{t(short ?? label)}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <div className="chat-history-desktop"><ChatHistory /></div>
    </aside>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { tab } = useUI();
  const { t, state } = useSession();
  const isAdmin = state.account?.role === "admin";
  return (
    <div className={isAdmin ? "app app--admin" : "app"}>
      <a
        href="#main"
        className="skip-link"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main")?.focus();
        }}
      >
        {t("skipToContent")}
      </a>
      <TopBar />
      {!isAdmin && <Nav />}
      <main id="main" className={`main ${tab === "ask" ? "main--chat" : ""}`} tabIndex={-1}>
        {children}
      </main>
      <DrawerHost />
    </div>
  );
}
