import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

# Import app components
from database import Base, get_db
import models
from main import app
import services.line_service
import services.gemini_service

from sqlalchemy.pool import StaticPool

# Create in-memory SQLite engine for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Drop tables
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_external_services(monkeypatch):
    """Automatically mock all network-calling services."""
    import api.webhook
    import api.scheduler
    
    mock_line_api = MagicMock()
    mock_line_api.get_profile.return_value = MagicMock(display_name="Test User")
    
    mock_reply_text = MagicMock()
    mock_push_text = MagicMock()
    mock_send_daily_question = MagicMock()
    mock_send_question_selection = MagicMock()
    mock_send_settings_menu = MagicMock()
    mock_generate_weekly_report = MagicMock(return_value="Mocked AI report for the week.")
    
    # Patch in api.webhook
    monkeypatch.setattr(api.webhook, "line_bot_api", mock_line_api)
    monkeypatch.setattr(api.webhook, "reply_text", mock_reply_text)
    monkeypatch.setattr(api.webhook, "send_question_selection", mock_send_question_selection)
    monkeypatch.setattr(api.webhook, "send_settings_menu", mock_send_settings_menu)
    
    # Patch in api.scheduler
    monkeypatch.setattr(api.scheduler, "send_daily_question", mock_send_daily_question)
    monkeypatch.setattr(api.scheduler, "push_text", mock_push_text)
    monkeypatch.setattr(api.scheduler, "generate_weekly_report", mock_generate_weekly_report)
    
    return {
        "line_api": mock_line_api,
        "reply_text": mock_reply_text,
        "push_text": mock_push_text,
        "send_daily_question": mock_send_daily_question,
        "send_question_selection": mock_send_question_selection,
        "send_settings_menu": mock_send_settings_menu,
        "generate_weekly_report": mock_generate_weekly_report
    }
