import pytest


BASE_REQUEST = {
    "event_name": "Python Backend Workshop",
    "organization": "Example Institute",
    "certificate_date": "2026-10-07",
    "recipients": [{"name": "Arun Kumar", "email": "arun@example.com"}],
}


@pytest.mark.parametrize(
    "changes",
    [
        {"recipients": []},
        {"recipients": [{"name": " ", "email": "arun@example.com"}]},
        {"recipients": [{"email": "arun@example.com"}]},
        {"recipients": [{"name": "Arun Kumar", "email": "not-an-email"}]},
        {"organization": "  "},
        {"event_name": ""},
        {"certificate_date": "not-a-date"},
    ],
)
def test_invalid_generation_requests_return_422(client, changes):
    body = {**BASE_REQUEST, **changes}

    response = client.post("/api/v1/jobs", json=body)

    assert response.status_code == 422
    assert response.json()["detail"]


def test_missing_required_fields_return_422(client):
    response = client.post("/api/v1/jobs", json={"recipients": []})

    assert response.status_code == 422


def test_batch_larger_than_configured_maximum_is_rejected(client):
    recipients = [
        {"name": f"Participant {index}", "email": f"person{index}@example.com"}
        for index in range(501)
    ]
    body = {**BASE_REQUEST, "recipients": recipients}

    response = client.post("/api/v1/jobs", json=body)

    assert response.status_code == 422
