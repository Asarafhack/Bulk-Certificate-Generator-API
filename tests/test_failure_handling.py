from app.services import job_service


def test_one_certificate_failure_does_not_stop_the_batch(client, monkeypatch):
    original_generator = job_service.generate_certificate_pdf

    def fail_one_recipient(certificate_id, recipient_name, *args, **kwargs):
        if recipient_name == "Will Fail":
            raise RuntimeError("simulated renderer problem")
        return original_generator(certificate_id, recipient_name, *args, **kwargs)

    monkeypatch.setattr(job_service, "generate_certificate_pdf", fail_one_recipient)
    response = client.post(
        "/api/v1/jobs",
        json={
            "event_name": "Python Backend Workshop",
            "organization": "Example Institute",
            "certificate_date": "2026-10-07",
            "recipients": [
                {"name": "Arun Kumar", "email": "arun@example.com"},
                {"name": "Will Fail", "email": "fail@example.com"},
                {"name": "Priya Devi", "email": "priya@example.com"},
                {"name": "Maya Rao", "email": "maya@example.com"},
                {"name": "Samir Shah", "email": "samir@example.com"},
            ],
        },
    )

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "completed_with_errors"
    assert job["successful"] == 4
    assert job["failed"] == 1
    assert job["pending"] == 0

    certificates = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["certificates"]
    failed = next(item for item in certificates if item["recipient_name"] == "Will Fail")
    successful = [item for item in certificates if item["status"] == "completed"]
    assert "RuntimeError" in failed["error_message"]
    assert failed["download_url"] is None
    assert len(successful) == 4
    assert all(
        client.get(item["download_url"]).status_code == 200
        for item in successful
    )
    failed_download = client.get(f"/api/v1/certificates/{failed['certificate_id']}")
    assert failed_download.status_code == 422
