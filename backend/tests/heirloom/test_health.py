def test_health_envelope(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"status": "ok"}
    assert body["meta"]["mode"] == "demo"
    assert body["meta"]["revision"] == 0
    assert body["meta"]["consent_revision"] == 0
    assert body["meta"]["degraded"] == []
    assert body["errors"] == []
    assert response.headers["cache-control"] == "no-store"


def test_unknown_route_uses_error_envelope(client):
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    body = response.json()
    assert body["data"] is None
    assert body["errors"][0]["code"] == "not_found"
    assert response.headers["cache-control"] == "no-store"
