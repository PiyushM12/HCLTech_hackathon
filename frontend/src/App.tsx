import { SessionProvider, useSession } from "./state/session";
import { UIProvider, useUI } from "./state/ui";
import { ChatProvider } from "./state/chat";
import { AppShell } from "./components/AppShell";
import { AskPage } from "./pages/AskPage";
import { EligibilityPage } from "./pages/EligibilityPage";
import { SchemesPage } from "./pages/SchemesPage";
import { SourcesPage } from "./pages/SourcesPage";
import { AdminPage } from "./pages/AdminPage";
import { LandingPage } from "./pages/LandingPage";

function UserPage() {
  const { tab } = useUI();
  switch (tab) {
    case "eligibility":
      return <EligibilityPage />;
    case "schemes":
      return <SchemesPage />;
    case "sources":
      return <SourcesPage />;
    default:
      return <AskPage />;
  }
}

export default function App() {
  return (
    <SessionProvider>
      <SignedInApp />
    </SessionProvider>
  );
}

function SignedInApp() {
  const { state: { account }, checkingAccount } = useSession();
  if (checkingAccount || !account) return <LandingPage />;

  return (
    <UIProvider key={account.username} role={account.role}>
      {account.role === "admin" ? (
        <AppShell><AdminPage /></AppShell>
      ) : (
        <ChatProvider>
          <AppShell><UserPage /></AppShell>
        </ChatProvider>
      )}
    </UIProvider>
  );
}
