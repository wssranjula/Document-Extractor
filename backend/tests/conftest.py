import os
from pathlib import Path

TEST_DIR = Path(__file__).parent
os.environ["SKIP_MIGRATIONS"] = "1"
os.environ["JWT_SECRET"] = "test-secret-key-with-enough-length"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DIR / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(TEST_DIR / "uploads")

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)
