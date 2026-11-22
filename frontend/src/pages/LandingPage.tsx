import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  ArrowRight, BadgeCheck, CalendarCheck, CheckCircle2, ClipboardCheck, FileSearch, Languages, Lock,
  MessagesSquare, Scale, ShieldCheck, Sparkles, UserRound, UsersRound,
} from "lucide-react";
import { errorMessage } from "../api";
import { Logo, Spinner, Wordmark } from "../components/common";
import { LanguageSelect } from "../components/TopBar";
import { useSession } from "../state/session";
import type { AccountRole } from "../types";
import "./landing.css";

type Route = "home" | "login" | "register";

function routeFromHash(): Route {
  const h = window.location.hash;
  if (h === "#/register") return "register";
  if (h === "#/login") return "login";
  return "home";
}

/** Fade/slide an element in once when it scrolls into view. */
function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") { setShown(true); return; }
    const io = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setShown(true); io.disconnect(); }
    }, { threshold: 0.15 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} className={`reveal ${shown ? "is-in" : ""} ${className}`} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}

function CountUp({ to, suffix = "" }: { to: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [value, setValue] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || typeof IntersectionObserver === "undefined") { setValue(to); return; }
    let raf = 0;
    const io = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      io.disconnect();
      const start = performance.now();
      const tick = (now: number) => {
        const p = Math.min((now - start) / 1200, 1);
        setValue(Math.round(to * (1 - Math.pow(1 - p, 3))));
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }, { threshold: 0.6 });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [to]);
  return <span ref={ref}>{value}{suffix}</span>;
}

/** A looping mock conversation that shows what the product does. */
const DEMO_LINES = [
  { who: "user", text: "मेरी माँ 67 साल की हैं, परिवार की आय ₹1.2 लाख है। क्या उन्हें पेंशन मिलेगी?" },
  { who: "bot", text: "हाँ — वे वृद्धावस्था पेंशन के लिए पात्र लगती हैं।", cite: "GL-PEN-01 · धारा 3" },
  { who: "bot", text: "ज़रूरी दस्तावेज़: आधार, आयु प्रमाण, आय प्रमाणपत्र। क्या मैं सेवा केंद्र में स्लॉट बुक करूँ?", cite: "GL-PEN-01 · धारा 5" },
] as const;

function ChatPreview() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setCount(DEMO_LINES.length); return; }
    const id = window.setTimeout(() => setCount((c) => (c >= DEMO_LINES.length + 2 ? 0 : c + 1)), count === 0 ? 900 : 1700);
    return () => window.clearTimeout(id);
  }, [count]);
  const typing = count > 0 && count < DEMO_LINES.length && DEMO_LINES[count].who === "bot";
  return (
    <div className="preview" aria-hidden="true">
      <div className="preview-bar"><i /><i /><i /><span>SchemeSathi</span></div>
      <div className="preview-body">
        {DEMO_LINES.slice(0, Math.min(count, DEMO_LINES.length)).map((l, i) => (
          <div key={i} className={`pv-msg pv-msg--${l.who}`}>
            <p>{l.text}</p>
            {"cite" in l && <span className="pv-cite"><BadgeCheck size={13} /> {l.cite}</span>}
          </div>
        ))}
        {typing && <div className="pv-msg pv-msg--bot pv-typing"><span /><span /><span /></div>}
      </div>
    </div>
  );
}

const FEATURES = [
  { Icon: Scale, title: "Verified eligibility", text: "A deterministic rule engine decides — never the language model. Every verdict shows rule by rule why." },
  { Icon: Languages, title: "Speaks your language", text: "Hindi, English, Kannada, Tamil and Hinglish. Replies come back in your own script, with the same numbers." },
  { Icon: FileSearch, title: "Cited answers", text: "Each answer points to the exact guideline or circular and section it came from." },
  { Icon: CalendarCheck, title: "Safe actions", text: "Draft an application or book a centre visit. Nothing happens until you confirm, and it is verified after." },
  { Icon: UsersRound, title: "Human hand-off", text: "When policy needs an officer, you get a referral with a full, PII-redacted bundle." },
  { Icon: Lock, title: "Private by design", text: "Profile data is used only with your consent. Personal details are redacted everywhere else." },
] as const;

const STEPS = [
  { Icon: MessagesSquare, title: "Ask in your words", text: "Type a question the way you would say it to a neighbour." },
  { Icon: ClipboardCheck, title: "Answer a few questions", text: "We ask only what the rules need — at most two at a time." },
  { Icon: CheckCircle2, title: "Get a verified answer", text: "See schemes you appear eligible for, documents and deadlines." },
  { Icon: Sparkles, title: "Take the next step", text: "Prepare a draft, book a visit, or set a reminder." },
] as const;

function Header({ route }: { route: Route }) {
  const { t } = useSession();
  return (
    <header className="lp-header">
      <a href="#/" className="brand lp-brand"><Logo size={38} /><Wordmark /></a>
      <nav className="lp-nav" aria-label="Sections">
        {route === "home" && (<><a href="#features">Features</a><a href="#how">How it works</a><a href="#languages">Languages</a></>)}
      </nav>
      <div className="lp-header-actions">
        <LanguageSelect />
        {route !== "login" && <a className="btn btn--ghost lp-login" href="#/login">{t("signIn")}</a>}
        {route !== "register" && <a className="btn btn--primary lp-register" href="#/register">{t("createAccount")}</a>}
      </div>
    </header>
  );
}

function Home() {
  const { t } = useSession();
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <span className="hero-eyebrow"><Sparkles size={14} aria-hidden="true" /> {t("demoPill")}</span>
          <h1>
            Welfare schemes,<br /><span className="grad-text">explained in your language.</span>
          </h1>
          <p className="hero-lead">
            Ask a question, answer a few details, and get a verified answer on what you can claim — with the source cited and no jargon.
          </p>
          <div className="hero-cta">
            <a className="btn btn--primary btn--lg" href="#/register">{t("createAccount")} <ArrowRight size={18} aria-hidden="true" /></a>
            <a className="btn btn--secondary btn--lg" href="#/login">{t("signIn")}</a>
          </div>
          <ul className="hero-trust">
            <li><ShieldCheck size={16} aria-hidden="true" /> Rule-engine verified</li>
            <li><BadgeCheck size={16} aria-hidden="true" /> Every answer cited</li>
            <li><Lock size={16} aria-hidden="true" /> Consent first</li>
          </ul>
        </div>
        <div className="hero-visual">
          <div className="orb orb--a" /><div className="orb orb--b" />
          <ChatPreview />
          <div className="float-chip float-chip--1"><CheckCircle2 size={16} /> Appears eligible</div>
          <div className="float-chip float-chip--2"><CalendarCheck size={16} /> Visit booked · Sat 10:30</div>
        </div>
      </section>

      <section className="stats" aria-label="At a glance">
        {[
          { n: 9, s: "", l: "welfare schemes" },
          { n: 4, s: "", l: "languages + Hinglish" },
          { n: 75, s: "", l: "cited sources" },
          { n: 100, s: "%", l: "rule-based verdicts" },
        ].map((x, i) => (
          <Reveal key={x.l} delay={i * 80} className="stat">
            <strong><CountUp to={x.n} suffix={x.s} /></strong><span>{x.l}</span>
          </Reveal>
        ))}
      </section>

      <section id="features" className="lp-section">
        <Reveal><h2 className="lp-h2">Built so the answer is right — then simple</h2>
          <p className="lp-sub">Everything that must be correct is code over rules. The language model only helps with wording.</p></Reveal>
        <div className="feature-grid">
          {FEATURES.map(({ Icon, title, text }, i) => (
            <Reveal key={title} delay={i * 70} className="feature">
              <span className="feature-icon"><Icon size={22} aria-hidden="true" /></span>
              <h3>{title}</h3><p>{text}</p>
            </Reveal>
          ))}
        </div>
      </section>

      <section id="how" className="lp-section lp-section--tint">
        <Reveal><h2 className="lp-h2">From question to next step in four moves</h2></Reveal>
        <ol className="steps">
          {STEPS.map(({ Icon, title, text }, i) => (
            <Reveal key={title} delay={i * 90} className="step">
              <span className="step-no">{i + 1}</span>
              <Icon size={22} aria-hidden="true" />
              <h3>{title}</h3><p>{text}</p>
            </Reveal>
          ))}
        </ol>
      </section>

      <section id="languages" className="lp-section">
        <Reveal><h2 className="lp-h2">One answer, every language</h2>
          <p className="lp-sub">Numbers, dates and verdicts are identical in every language by construction.</p></Reveal>
        <div className="lang-cloud">
          {["हिन्दी", "English", "ಕನ್ನಡ", "தமிழ்", "Hinglish"].map((l, i) => (
            <Reveal key={l} delay={i * 80} className="lang-pill">{l}</Reveal>
          ))}
        </div>
      </section>

      <Reveal className="cta-band">
        <h2>Find out what you can claim today</h2>
        <div className="hero-cta hero-cta--center">
          <a className="btn btn--accent btn--lg" href="#/register">{t("createAccount")} <ArrowRight size={18} aria-hidden="true" /></a>
          <a className="btn btn--glass btn--lg" href="#/login">{t("signIn")}</a>
        </div>
      </Reveal>

      <footer className="lp-footer">
        <span>{t("demoPill")}</span>
        <span>All schemes, amounts and offices are fictional · Mitrapur Pradesh</span>
      </footer>
    </>
  );
}

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
      <p className="landing-auth-link">{t("alreadyHaveAccount")} <a href="#/login">{t("signIn")}</a></p>
    </>
  );
}

function AuthScreen({ registering }: { registering: boolean }) {
  const { t, checkingAccount } = useSession();
  return (
    <main className="auth">
      <aside className="auth-side" aria-hidden="true">
        <div className="orb orb--a" /><div className="orb orb--b" />
        <h2>Know what you can claim.<br />Without the paperwork maze.</h2>
        <ul>
          <li><CheckCircle2 size={18} /> Verified, rule-based eligibility</li>
          <li><CheckCircle2 size={18} /> Answers in your language, with sources</li>
          <li><CheckCircle2 size={18} /> You confirm every action</li>
        </ul>
      </aside>
      <section className="landing-card auth-card" aria-labelledby="landing-auth-title" key={registering ? "r" : "l"}>
        <a href="#/" className="auth-back">← Back to home</a>
        <h1 id="landing-auth-title" className="auth-title">{t(registering ? "createAccount" : "signIn")}</h1>
        {checkingAccount ? <Spinner label={t("loading")} /> : registering ? <RegistrationForm /> : <SignInForm />}
      </section>
    </main>
  );
}

export function LandingPage() {
  const [route, setRoute] = useState<Route>(routeFromHash);
  useEffect(() => {
    const update = () => { setRoute(routeFromHash()); document.querySelector(".landing")?.scrollTo({ top: 0 }); };
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  return (
    <div className="landing">
      <div className="lp-bg" aria-hidden="true" />
      <Header route={route} />
      {route === "home" ? <Home /> : <AuthScreen registering={route === "register"} />}
    </div>
  );
}
