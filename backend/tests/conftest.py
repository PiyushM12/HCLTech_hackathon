"""Tests run fully offline: MOCK_LLM, a throwaway runtime dir and the hash embedder (fast;
cross-lingual retrieval quality is measured separately in eval/, with the real model)."""
import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="schemesathi-test-")
os.environ.setdefault("MOCK_LLM", "true")
os.environ.setdefault("EMBEDDING_BACKEND", "hash")
os.environ["RUNTIME_DIR"] = _tmp
os.environ["DB_PATH"] = str(Path(_tmp) / "test.db")
os.environ["CHROMA_DIR"] = str(Path(_tmp) / "chroma")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

AS_OF = "2026-11-21"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def conn(client):
    from app import db
    c = db.connect()
    yield c
    c.close()


@pytest.fixture(scope="session")
def account_client(client):
    from contextlib import ExitStack
    from fastapi.testclient import TestClient
    from app.auth import create_account

    password = "temporary-test-password"
    accounts = {}
    with ExitStack() as stack:
        def get_account(citizen_id=None):
            if citizen_id not in accounts:
                username = citizen_id.lower() if citizen_id else "test-admin"
                role = "user" if citizen_id else "admin"
                create_account(username, password, role, citizen_id)
                signed_in = TestClient(client.app)
                stack.callback(signed_in.close)
                response = signed_in.post("/auth/login", json={"username": username, "password": password, "role": role})
                assert response.status_code == 200, response.text
                accounts[citizen_id] = signed_in
            return accounts[citizen_id]

        yield get_account
