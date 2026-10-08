from datetime import date

from app import database
from app.models import Certificate, GenerationJob


def test_certificate_list_and_download(client):
    response = client.post(
        "/api/v1/jobs",
        json={
            "event_name": "Python Backend Workshop",
            "organization": "Example Institute",
            "certificate_date": "2026-10-07",
            "recipients": [{"name": "Arun Kumar", "email": "arun@example.com"}],
        },
    )
    job_id = response.json()["job_id"]

    certificate_list = client.get(f"/api/v1/jobs/{job_id}/certificates")
    certificate = certificate_list.json()["certificates"][0]
    assert certificate_list.status_code == 200
    assert certificate["status"] == "completed"
    assert certificate["recipient_name"] == "Arun Kumar"
    assert certificate["recipient_email"] == "arun@example.com"
    assert certificate["download_url"] == f"/api/v1/certificates/{certificate['certificate_id']}"

    download = client.get(certificate["download_url"])
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content.startswith(b"%PDF-")


def test_certificate_not_found_returns_404(client):
    response = client.get("/api/v1/certificates/71ca271a-7d4e-45e5-8ef0-d892562d64bd")

    assert response.status_code == 404


def test_certificate_not_ready_returns_409(client):
    job_id = "da30a155-a2f2-46fb-9a2d-8ccb069605c2"
    certificate_id = "cf806826-9cf9-470b-a4c0-c05163a8b365"
    with database.SessionLocal() as db:
        db.add(
            GenerationJob(
                id=job_id,
                status="processing",
                event_name="Workshop",
                organization="Example Institute",
                certificate_date=date(2026, 10, 7),
                total_count=1,
                successful_count=0,
                failed_count=0,
                certificates=[
                    Certificate(
                        id=certificate_id,
                        recipient_name="Arun Kumar",
                        recipient_email="arun@example.com",
                        status="pending",
                    )
                ],
            )
        )
        db.commit()

    response = client.get(f"/api/v1/certificates/{certificate_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Certificate is not ready yet."
