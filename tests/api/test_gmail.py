# tests/api/test_gmail.py
def test_application_model_has_email_status():
    from src.data.models.application import Application
    assert hasattr(Application, "email_status")
