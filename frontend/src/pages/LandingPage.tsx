import { useEffect, useState, type FormEvent } from "react";
import { ArrowRight, ShieldCheck, UserRound } from "lucide-react";
import { errorMessage } from "../api";
import { Logo, Spinner, Wordmark } from "../components/common";
import { LanguageSelect } from "../components/TopBar";
import { useSession } from "../state/session";
import type { AccountRole } from "../types";
import "./landing.css";

const ROLES = [
  { value: "user", label: "userRole", description: "userRoleDescription", Icon: UserRound },
  { value: "admin", label: "navAdmin", description: "adminRoleDescription", Icon: ShieldCheck },
] as const;

function UsernameField({ registering = false }: { registering?: boolean }) {
  const { t } = useSession();
  return (
    <label className="field">
      <span className="field-label">{t("username")}</span>
      <input name="username" autoComplete="username" autoCapitalize="none" spellCheck={false}
        minLength={registering ? 3 : undefined} maxLength={64} required />
    </label>
  );
}

function AuthSubmit({ label, busy }: { label: string; busy: boolean }) {
  const { t } = useSession();
  return (
    <button className="btn btn--primary landing-submit" type="submit" disabled={busy}>
      {busy ? <Spinner label={t("loading")} /> : <>{label}<ArrowRight size={18} aria-hidden="true" /></>}
    </button>
  );
}

function SignInForm() {
  const { t, signIn } = useSession();
  const [role, setRole] = useState<AccountRole>("user");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const roleLabel = t(role === "user" ? "userRole" : "navAdmin");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const fields = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await signIn(role, String(fields.get("username") ?? ""), String(fields.get("password") ?? ""));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <fieldset className="landing-roles" disabled={busy}>
        <legend>{t("chooseRole")}</legend>
        <div className="landing-role-options">
          {ROLES.map(({ value, label, description, Icon }) => (
            <label className="landing-role" key={value}>
              <input type="radio" name="role" value={value} checked={role === value} aria-label={t(label)}
                onChange={() => { setRole(value); setError(null); }} />
              <span className="landing-role-card">
                <Icon size={21} aria-hidden="true" />
                <strong>{t(label)}</strong>
                <span>{t(description)}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <form className="landing-form" onSubmit={(event) => void submit(event)} key={role}>
        <UsernameField />
        <label className="field">
          <span className="field-label">{t("password")}</span>
          <input name="password" type="password" autoComplete="current-password" maxLength={128} required />
        </label>
        {error && <p className="landing-error small error-text" role="alert">{error}</p>}
        <AuthSubmit label={t("signInAsRole", { role: roleLabel })} busy={busy} />
      </form>
      {role === "user" && (
        <p className="landing-auth-link">{t("newToSchemeSathi")} <a href="#/register">{t("createAccount")}</a></p>
      )}
    </>
  );
}

function RegistrationForm() {
  const { t, register } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const fields = new FormData(event.currentTarget);
    const password = String(fields.get("password") ?? "");
    if (password !== fields.get("confirmation")) {
      setError(t("passwordMismatch"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await register(String(fields.get("username") ?? ""), password, fields.has("consent"));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <p className="landing-form-intro">{t("registrationIntro")}</p>
      <form className="landing-form" onSubmit={(event) => void submit(event)}>
        <UsernameField registering />
        <label className="field">
          <span className="field-label">{t("password")}</span>
          <input name="password" type="password" autoComplete="new-password" minLength={12}
            maxLength={128} required aria-describedby="registration-password-hint" />
          <span className="field-hint" id="registration-password-hint">{t("registrationPasswordHint")}</span>
        </label>
        <label className="field">
          <span className="field-label">{t("confirmPassword")}</span>
          <input name="confirmation" type="password" autoComplete="new-password" maxLength={128} required />
        </label>
        <label className="landing-consent">
          <input name="consent" type="checkbox" />
          <span>{t("registrationConsent")}</span>
        </label>
        {error && <p className="landing-error small error-text" role="alert">{error}</p>}
        <AuthSubmit label={t("createAccount")} busy={busy} />
      </form>
      <p className="landing-auth-link">{t("alreadyHaveAccount")} <a href="#/">{t("signIn")}</a></p>
    </>
  );
}

export function LandingPage() {
  const { t, checkingAccount } = useSession();
  const [registering, setRegistering] = useState(() => window.location.hash === "#/register");
  useEffect(() => {
    const update = () => setRegistering(window.location.hash === "#/register");
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  return (
    <div className="landing">
      <header className="landing-header">
        <div className="brand"><Logo size={40} /><Wordmark /></div>
        <LanguageSelect />
      </header>
      <main className="landing-main">
        <section className="landing-intro" aria-labelledby="landing-title">
          <h1 id="landing-title">{t("appTagline")}</h1>
          <p>{t("landingIntro")}</p>
          <span className="landing-demo">{t("demoPill")}</span>
        </section>
        <section className="landing-card" aria-labelledby="landing-auth-title">
          <h2 id="landing-auth-title">{t(registering ? "createAccount" : "signIn")}</h2>
          {checkingAccount ? <Spinner label={t("loading")} /> : registering ? <RegistrationForm /> : <SignInForm />}
        </section>
      </main>
    </div>
  );
}
