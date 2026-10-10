import pytest
from fastapi.testclient import TestClient

from app.heirloom.config import HeirloomSettings
from app.heirloom.db import SessionFactory
from app.main import create_app


@pytest.fixture
def settings() -> HeirloomSettings:
    return HeirloomSettings(mode="demo", database_url="sqlite://")


@pytest.fixture
def client(settings: HeirloomSettings):
    """TestClient over an in-memory DB that app startup has seeded (demo mode)."""
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def db_session(client: TestClient):
    """A session on the same in-memory database the seeded `client` talks to."""
    with SessionFactory(bind=client.app.state.engine) as session:
        yield session
