from tests.conftest import VALID_LEAD


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data_label": "DEMO DATA"}


def test_create_lead_is_qualified(client):
    response = client.post("/leads", json=VALID_LEAD)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["data_label"] == "DEMO DATA"
    assert body["qualification"]["tier"] == "hot"
    assert body["qualification"]["score"] == 90


def test_list_and_get_lead(client, auth_headers):
    client.post("/leads", json=VALID_LEAD)
    client.post("/leads", json={**VALID_LEAD, "budget": "10", "message": "just looking"})
    listed = client.get("/leads", headers=auth_headers).json()
    assert [lead["id"] for lead in listed] == [1, 2]
    assert listed[1]["qualification"]["tier"] == "cold"
    assert client.get("/leads/2", headers=auth_headers).json()["id"] == 2


def test_get_missing_lead_returns_404(client, auth_headers):
    assert client.get("/leads/999", headers=auth_headers).status_code == 404


def test_pagination_limits_are_validated(client, auth_headers):
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert client.get(f"/leads?{query}", headers=auth_headers).status_code == 422


def test_invalid_payloads_are_rejected(client):
    assert client.post("/leads", json={**VALID_LEAD, "budget": "-1"}).status_code == 422
    assert client.post("/leads", json={**VALID_LEAD, "name": ""}).status_code == 422
    assert client.post("/leads", json={**VALID_LEAD, "extra": "x"}).status_code == 422
    assert client.post("/leads", json={**VALID_LEAD, "data_label": "REAL"}).status_code == 422

def test_openapi_documents_auth_errors(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path in ("/leads", "/leads/{lead_id}"):
        assert {"401", "403", "503"} <= set(paths[path]["get"]["responses"])
