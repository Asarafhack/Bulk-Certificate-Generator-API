import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.main import app
from app.services import certificate_service


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_engine = database.build_engine(
        "sqlite://",
        poolclass=StaticPool,
    )
    test_sessions = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "SessionLocal", test_sessions)
    monkeypatch.setattr(certificate_service, "STORAGE_DIR", tmp_path / "certificates")
    database.initialize_database()

    with TestClient(app) as test_client:
        yield test_client

    test_engine.dispose()
