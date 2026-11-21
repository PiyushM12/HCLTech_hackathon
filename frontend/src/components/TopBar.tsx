import { useState } from "react";
import { ChevronDown, Globe, ShieldAlert, SlidersHorizontal, TriangleAlert, UserRound } from "lucide-react";
import { errorMessage } from "../api";
import { LANGUAGE_OPTIONS, type UiLanguage } from "../i18n";
import { useSession } from "../state/session";
import { formatDate, todayISO } from "../lib/format";
import { Logo, Wordmark } from "./common";
import { Popover } from "./Popover";

export function LanguageSelect() {
  const { t, state, dispatch } = useSession();
  const current = LANGUAGE_OPTIONS.find((o) => o.value === state.language) ?? LANGUAGE_OPTIONS[0];
  const isAuto = current.value === "auto";
  return (
    <div className="lang-select" title={t("language")}>
      <Globe size={18} aria-hidden="true" className="lang-select-icon" />
      <span className="lang-current" aria-hidden="true" lang={isAuto ? undefined : current.value}>
        <span className="lang-long">{isAuto ? t("autoDetect") : current.label}</span>
        <span className="lang-short">{isAuto ? t("autoShort") : current.label}</span>
      </span>
      <ChevronDown size={16} aria-hidden="true" className="lang-select-chev" />
      <select
        aria-label={t("language")}
        value={state.language}
        onChange={(e) => dispatch({ type: "setLanguage", language: e.target.value as UiLanguage })}
      >
        {LANGUAGE_OPTIONS.map((o) => (
          <option key={o.value} value={o.value} lang={o.value === "auto" ? undefined : o.value}>
            {o.value === "auto" ? t("autoDetect") : o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function AccountMenu() {
  const { t, state, signOut } = useSession();
  const { account } = state;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!account) return null;

  const noConsent = account.consent_given === "N";
  const name = account.username;
  const roleLabel = t(account.role === "admin" ? "navAdmin" : "userRole");

  async function leave() {
    setBusy(true);
    setError(null);
    try {
      await signOut();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Popover
      label={t("signedInAs")}
      trigger={(props) => (
        <button type="button" className={`id-btn ${noConsent ? "id-btn--warn" : ""}`} {...props}>
          <UserRound size={18} aria-hidden="true" />
          <span className="id-btn-text">
            <span className="id-btn-name">{name}</span>
            <span className="id-btn-sub">{roleLabel}</span>
          </span>
          <ChevronDown size={16} aria-hidden="true" className="hide-sm" />
        </button>
      )}
    >
      {() => (
        <>
          <div className="popover-title">{t("signedInAs")} {name}</div>
          {noConsent && (
            <p className="id-consent-note">
              <ShieldAlert size={16} aria-hidden="true" />
              {t("consentNoNote")}
            </p>
          )}
          {error && <p className="small error-text" role="alert">{error}</p>}
          <button className="btn btn--secondary" type="button" onClick={() => void leave()} disabled={busy}>
            {busy ? t("loading") : t("signOut")}
          </button>
        </>
      )}
    </Popover>
  );
}

function AdvancedMenu() {
  const { t, state, dispatch } = useSession();
  const today = todayISO();
  const value = state.asOfDate ?? today;
  const overridden = !!state.asOfDate;
  const uiLang = state.language === "auto" ? "en" : state.language;
  return (
    <Popover
      label={t("advanced")}
      trigger={(p) => (
        <button
          type="button"
          className={`icon-btn icon-btn--bordered ${overridden ? "has-dot" : ""}`}
          aria-label={t("advanced")}
          title={overridden ? t("testingAsOf", { date: formatDate(value, uiLang) }) : t("advanced")}
          {...p}
        >
          <SlidersHorizontal size={18} aria-hidden="true" />
        </button>
      )}
    >
      {() => (
        <div className="adv-panel">
          <div className="popover-title">{t("advanced")}</div>
          <label className="field">
            <span className="field-label">{t("asOfDate")}</span>
            <input
              type="date"
              value={value}
              onChange={(e) => {
                const v = e.target.value;
                dispatch({ type: "setAsOfDate", date: !v || v === today ? null : v });
              }}
            />
            <span className="field-hint">{t("asOfDateHint")}</span>
          </label>
          {overridden && (
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => dispatch({ type: "setAsOfDate", date: null })}
            >
              {t("resetToday")}
            </button>
          )}
        </div>
      )}
    </Popover>
  );
}

export function TopBar() {
  const { t, state } = useSession();
  const isAdmin = state.account?.role === "admin";
  return (
    <header className="topbar">
      <a className="brand" href={isAdmin ? "#/admin" : "#/ask"} aria-label="SchemeSathi">
        <Logo size={34} />
        <span className="brand-text">
          <Wordmark />
          <span className="brand-tagline">{t("appTagline")}</span>
        </span>
      </a>
      <span className="demo-pill" title={t("demoPill")}>
        <TriangleAlert size={14} aria-hidden="true" />
        <span className="demo-pill-long">{t("demoPill")}</span>
        <span className="demo-pill-short">{t("demoPillShort")}</span>
      </span>
      <div className="topbar-actions">
        <LanguageSelect />
        <AccountMenu />
        {!isAdmin && <AdvancedMenu />}
      </div>
    </header>
  );
}
