import os
import tempfile
from pathlib import Path

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="pronunciation_coach_test_"))
os.environ["PRONUNCIATION_COACH_DATA_DIR"] = str(_TEST_DATA_DIR)

# Dummy auth config: authlib only fetches OIDC metadata lazily, on the first
# call to authorize_redirect/authorize_access_token — no test exercises the
# real login flow, so these values are never actually used over the network.
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")
os.environ.setdefault(
    "AUTHENTIK_ISSUER", "http://authentik.invalid/application/o/test/"
)
os.environ.setdefault("AUTHENTIK_CLIENT_ID", "test-client-id")
os.environ.setdefault("AUTHENTIK_CLIENT_SECRET", "test-client-secret")

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import get_current_user
from app.db import engine
from app.main import app
from app.models import User


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        with Session(engine) as session:
            user = User(sub="test-sub", email="tester@example.com")
            session.add(user)
            session.commit()
            session.refresh(user)
        app.dependency_overrides[get_current_user] = lambda: user
        yield test_client
        app.dependency_overrides.pop(get_current_user, None)
