import os
import tempfile
from pathlib import Path

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="pronunciation_coach_test_"))
os.environ["PRONUNCIATION_COACH_DATA_DIR"] = str(_TEST_DATA_DIR)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
