def test_health_returns_ok():
    from fastapi.testclient import TestClient

    from src.api.app import create_app

    app = create_app()
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
