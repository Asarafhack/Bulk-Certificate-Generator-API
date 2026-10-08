from datetime import date

from sqlalchemy import select

from app import database
from app.models import Certificate, GenerationJob


def request_body(recipients=None):
    return {
        "event_name": "Python Backend Workshop",
        "organization": "Example Institute",
        "certificate_date": "2026-10-07",
        "recipients": recipients
        or [
            {"name": "Arun Kumar", "email": "arun@example.com"},
            {"name": "Priya Devi", "email": "priya@example.com"},
        ],
    }


def test_create_job_returns_accepted_and_processes_recipients(client):
    response = client.post("/api/v1/jobs", json=request_body())

    assert response.status_code == 202
    created = response.json()
    assert created["status"] == "pending"
    assert created["total"] == 2
    assert created["job_id"]

    status_response = client.get(f"/api/v1/jobs/{created['job_id']}")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["status"] == "completed"
    assert status_data["successful"] == 2
    assert status_data["failed"] == 0
    assert status_data["pending"] == 0
    assert status_data["progress_percentage"] == 100.0
    assert status_data["created_at"].endswith(("Z", "+00:00"))
    assert status_data["completed_at"].endswith(("Z", "+00:00"))


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_job_not_found_returns_404(client):
    response = client.get("/api/v1/jobs/71ca271a-7d4e-45e5-8ef0-d892562d64bd")

    assert response.status_code == 404
    assert response.json()["detail"] == "Generation job not found."


def test_job_status_calculates_partial_progress(client):
    job_id = "da30a155-a2f2-46fb-9a2d-8ccb069605c2"
    with database.SessionLocal() as db:
        db.add(
            GenerationJob(
                id=job_id,
                status="processing",
                event_name="Workshop",
                organization="Example Institute",
                certificate_date=date(2026, 10, 7),
                total_count=4,
                successful_count=1,
                failed_count=1,
            )
        )
        db.commit()

    response = client.get(f"/api/v1/jobs/{job_id}")
    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "processing"
    assert data["successful"] == 1
    assert data["failed"] == 1
    assert data["pending"] == 2
    assert data["progress_percentage"] == 50.0


def test_sqlite_foreign_key_cascades_certificate_records(client):
    job_id = "da30a155-a2f2-46fb-9a2d-8ccb069605c2"
    certificate_id = "cf806826-9cf9-470b-a4c0-c05163a8b365"
    with database.SessionLocal() as db:
        job = GenerationJob(
            id=job_id,
            status="pending",
            event_name="Workshop",
            organization="Example Institute",
            certificate_date=date(2026, 10, 7),
            total_count=1,
            successful_count=0,
            failed_count=0,
        )
        db.add_all(
            [
                job,
                Certificate(
                    id=certificate_id,
                    job_id=job_id,
                    recipient_name="Arun Kumar",
                    recipient_email="arun@example.com",
                    status="pending",
                ),
            ]
        )
        db.commit()

        db.delete(db.get(GenerationJob, job_id))
        db.commit()
        remaining_id = db.scalar(
            select(Certificate.id).where(Certificate.id == certificate_id)
        )
        assert remaining_id is None
