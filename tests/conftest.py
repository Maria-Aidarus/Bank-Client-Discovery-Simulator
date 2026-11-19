import shutil
import socket
from pathlib import Path

import pytest

from bank_simulator.data_loader import DEFAULT_DATA_DIR
from bank_simulator.models import InterviewSession
from bank_simulator.services.content_service import ContentService
from bank_simulator.services.interview_service import InterviewService
from bank_simulator.services.recommendation_service import RecommendationService


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Every pytest test must use an injected transport or agent double."""
    def reject_connection(*args, **kwargs):
        raise AssertionError("Network access is disabled during offline tests.")

    monkeypatch.setattr(socket.socket, "connect", reject_connection)
    monkeypatch.setattr(socket, "create_connection", reject_connection)






@pytest.fixture
def content() -> ContentService:
    return ContentService()


@pytest.fixture
def editable_data(tmp_path: Path) -> Path:
    return shutil.copytree(DEFAULT_DATA_DIR, tmp_path / "data")


@pytest.fixture
def interviews(content: ContentService) -> InterviewService:
    return InterviewService(content)


@pytest.fixture
def recommendations(content: ContentService) -> RecommendationService:
    return RecommendationService(content)


@pytest.fixture
def completed_interview(interviews: InterviewService) -> InterviewSession:
    session = interviews.create_session("mohamed")
    session = interviews.record_student_message(session, "  What are you saving for?\n")
    session = interviews.record_client_response(session, "A professional certification in 18 months.")
    return interviews.end_interview(session)
