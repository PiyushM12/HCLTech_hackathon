"""Local accounts and revocable browser sessions."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from . import config, db

COOKIE = "schemesathi_session"
SESSION_SECONDS = 8 * 60 * 60
LOGIN_WINDOW_SECONDS = 5 * 60
MAX_LOGIN_ATTEMPTS = 10
USERNAME_PATTERN = r"[a-z0-9][a-z0-9_.-]{2,63}"
router = APIRouter(prefix="/auth", tags=["auth"])


@dataclass(frozen=True)
class Session:
    owner_id: str
    role: Literal["guest", "user", "admin"]
    username: str | None = None

    def can_read(self, owner_id: str) -> bool:
        return self.role == "admin" or self.owner_id == owner_id


class Credentials(BaseModel):
    username: str = Field(max_length=64)
    password: SecretStr = Field(max_length=128, repr=False)
    role: Literal["user", "admin"]


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(max_length=64)
    password: SecretStr = Field(min_length=12, max_length=128, repr=False)
    consent: bool = False


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**15, r=8, p=3, maxmem=64 * 1024**2)


def _validate_username(username: str) -> str:
    username = username.strip().lower()
    if not re.fullmatch(USERNAME_PATTERN, username):
        raise ValueError("Use a username of 3–64 letters, digits, periods, underscores or hyphens.")
    return username


def _hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError("Use a password of 12–128 characters.")
    salt = secrets.token_bytes(16)
    return f"{salt.hex()}:{_password_digest(password, salt).hex()}"


def create_account(username: str, password: str, role: str, citizen_id: str | None = None) -> None:
    username = _validate_username(username)
    if (role == "user" and not citizen_id) or (role == "admin" and citizen_id is not None):
        raise ValueError("A user must be linked to a citizen ID. An admin has no citizen ID.")
    if role not in {"user", "admin"}:
        raise ValueError("Role must be user or admin.")
    password_hash = _hash_password(password)
    with db.get_conn() as conn:
        if citizen_id and (citizen_id == "guest" or ":" in citizen_id or not db.row(
            conn, "SELECT 1 FROM citizens WHERE citizen_id=?", (citizen_id,)
        )):
            raise ValueError("Unknown or reserved citizen ID.")
        try:
            conn.execute("INSERT INTO auth_accounts VALUES (?, ?, ?, ?)",
                         (username, password_hash, role, citizen_id))
        except sqlite3.IntegrityError as exc:
            raise ValueError("That username or citizen ID already has an account.") from exc


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _request_token(request: Request) -> str | None:
    if request.method == "POST" and request.headers.get("Sec-Fetch-Site") in {"cross-site", "same-site"}:
        raise HTTPException(403, "Use the app's own origin to make this request.")
    token = request.cookies.get(COOKIE, "")
    return token if re.fullmatch(r"[A-Za-z0-9_-]{43}", token) else None


def _session_for_row(row: dict) -> Session:
    if row["role"] == "user":
        return Session(row["citizen_id"], "user", row["username"])
    if row["role"] == "admin":
        return Session(f"admin:{row['username']}", "admin", row["username"])
    return Session(row["guest_id"], "guest")


def get_session(request: Request) -> Session | None:
    token = _request_token(request)
    if not token:
        return None
    with db.get_conn() as conn:
        row = db.row(conn, """SELECT s.guest_id, a.username, a.role, a.citizen_id FROM auth_sessions s
            LEFT JOIN auth_accounts a ON a.username=s.username
            WHERE s.token_hash=? AND s.expires_at>? AND (s.guest_id IS NOT NULL OR a.username IS NOT NULL)""",
                     (_token_hash(token), int(time.time())))
    return _session_for_row(row) if row else None


def _store_session(conn: sqlite3.Connection, previous: str | None, session: Session) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    conn.execute("DELETE FROM auth_sessions WHERE expires_at<=?", (now,))
    if previous:
        conn.execute("DELETE FROM auth_sessions WHERE token_hash=?", (_token_hash(previous),))
    conn.execute("INSERT INTO auth_sessions VALUES (?, ?, ?, ?)",
                 (_token_hash(token), session.username, session.owner_id if session.role == "guest" else None,
                  now + SESSION_SECONDS))
    return token


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                        samesite="strict", secure=config.AUTH_COOKIE_SECURE)


def _issue_session(request: Request, response: Response, session: Session) -> None:
    previous = _request_token(request)
    with db.get_conn() as conn:
        token = _store_session(conn, previous, session)
    _set_session_cookie(response, token)


def chat_session(request: Request, response: Response, session: Session | None = Depends(get_session)) -> Session:
    if session is None:
        session = Session(f"guest:{uuid.uuid4().hex}", "guest")
        _issue_session(request, response, session)
    return session


def require_admin(session: Session | None = Depends(get_session)) -> Session:
    if not session or session.role == "guest":
        raise HTTPException(401, "Sign in as an admin.")
    if session.role != "admin":
        raise HTTPException(403, "Admin access is required.")
    return session


def require_user(session: Session | None = Depends(get_session)) -> Session:
    if not session or session.role == "guest":
        raise HTTPException(401, "Sign in as a citizen.")
    if session.role != "user":
        raise HTTPException(403, "Citizen access is required.")
    return session


def _record_login_attempt(username: str, client_ip: str) -> None:
    now = int(time.time())
    with db.get_conn() as conn:
        conn.execute("DELETE FROM auth_login_attempts WHERE expires_at<=?", (now,))
        attempt = conn.execute("""INSERT INTO auth_login_attempts VALUES (?, ?, ?, 1)
            ON CONFLICT(username, client_ip) DO UPDATE SET attempts=attempts+1
            WHERE attempts<? RETURNING attempts""",
                               (username, client_ip, now + LOGIN_WINDOW_SECONDS, MAX_LOGIN_ATTEMPTS)).fetchone()
    if attempt is None:
        raise HTTPException(429, "Too many sign-in attempts. Try again in a few minutes.",
                            headers={"Retry-After": str(LOGIN_WINDOW_SECONDS)})


def _profile(session: Session | None) -> dict | None:
    if not session or session.role == "guest":
        return None
    profile = {"username": session.username, "role": session.role}
    if session.role == "user":
        with db.get_conn() as conn:
            citizen = db.row(conn, "SELECT citizen_id, district, consent_given FROM citizens WHERE citizen_id=?",
                             (session.owner_id,))
        profile.update(citizen or {"citizen_id": session.owner_id})
    return profile


@router.post("/login")
def login(credentials: Credentials, request: Request, response: Response) -> dict:
    _request_token(request)
    username = credentials.username.strip().lower()
    client_ip = request.client.host if request.client else ""
    _record_login_attempt(username, client_ip)
    with db.get_conn() as conn:
        row = db.row(conn, "SELECT * FROM auth_accounts WHERE username=?", (username,))
    # Spend comparable time on unknown accounts and incorrect passwords.
    stored = row["password_hash"] if row else f"{'00' * 16}:{'00' * 64}"
    salt, expected = (bytes.fromhex(part) for part in stored.split(":"))
    if not hmac.compare_digest(_password_digest(credentials.password.get_secret_value(), salt), expected) or row is None:
        raise HTTPException(401, "Invalid username or password.")
    with db.get_conn() as conn:
        conn.execute("DELETE FROM auth_login_attempts WHERE username=? AND client_ip=?", (username, client_ip))
    if row["role"] != credentials.role:
        raise HTTPException(403, "This account belongs to a different role. Switch roles and try again.")
    session = _session_for_row(row)
    _issue_session(request, response, session)
    return {"account": _profile(session)}


@router.post("/register", status_code=201)
def register(registration: Registration, request: Request, response: Response) -> dict:
    previous = _request_token(request)
    try:
        username = _validate_username(registration.username)
        password_hash = _hash_password(registration.password.get_secret_value())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    # Keep self-registered IDs outside the C0000–C9999 range used by CSV imports.
    citizen_id = f"USR-{uuid.uuid4().hex.upper()}"
    consent = "Y" if registration.consent else "N"
    session = Session(citizen_id, "user", username)
    with db.get_conn() as conn:
        conn.execute("INSERT INTO citizens (citizen_id, consent_given) VALUES (?, ?)", (citizen_id, consent))
        created = conn.execute("""INSERT INTO auth_accounts (username, password_hash, role, citizen_id)
            VALUES (?, ?, 'user', ?) ON CONFLICT(username) DO NOTHING""", (username, password_hash, citizen_id))
        if not created.rowcount:
            raise HTTPException(409, "That username is already taken. Choose another or sign in.")
        token = _store_session(conn, previous, session)
    _set_session_cookie(response, token)
    return {"account": {"username": username, "role": "user", "citizen_id": citizen_id, "consent_given": consent}}


@router.get("/me")
def me(session: Session = Depends(chat_session)) -> dict:
    return {"account": _profile(session)}


@router.post("/logout", status_code=204)
def logout(request: Request) -> Response:
    token = _request_token(request)
    if token:
        with db.get_conn() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token_hash=?", (_token_hash(token),))
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, httponly=True, samesite="strict", secure=config.AUTH_COOKIE_SECURE)
    return response
