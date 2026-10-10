import pytest
from fastapi.testclient import TestClient

from app.heirloom.config import HeirloomSettings
from app.main import create_app


@pytest.fixture
def settings() -> HeirloomSettings:
    return HeirloomSettings(mode="demo", database_url="sqlite://")


@pytest.fixture
def client(settings: HeirloomSettings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
