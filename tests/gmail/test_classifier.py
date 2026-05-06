from unittest.mock import MagicMock
import pytest
from src.gmail.classifier import classify_email, EmailStatus


def _mock_anthropic(response_text: str):
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=response_text)]
    client.messages.create.return_value = msg
    return client


def test_classify_interview_request():
    status = classify_email("Let's schedule a call", "We'd like to invite you for an interview.", _mock_anthropic("interview_request"))
    assert status == EmailStatus.INTERVIEW_REQUEST


def test_classify_rejection():
    status = classify_email("Your application status", "We regret to inform you.", _mock_anthropic("rejection"))
    assert status == EmailStatus.REJECTION


def test_classify_offer():
    status = classify_email("Job Offer", "We are pleased to offer you the position.", _mock_anthropic("offer"))
    assert status == EmailStatus.OFFER


def test_classify_defaults_to_other_on_unknown():
    status = classify_email("Re: hi", "Ok thanks", _mock_anthropic("something_unknown"))
    assert status == EmailStatus.OTHER


def test_classify_follow_up_needed():
    status = classify_email("Checking in", "Just wanted to see if you're still interested.", _mock_anthropic("follow_up_needed"))
    assert status == EmailStatus.FOLLOW_UP_NEEDED
