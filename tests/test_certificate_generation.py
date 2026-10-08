from datetime import date

from app.services.certificate_service import generate_certificate_pdf


def test_certificate_generation_creates_readable_pdf(tmp_path, monkeypatch):
    import app.services.certificate_service as certificate_service

    monkeypatch.setattr(certificate_service, "STORAGE_DIR", tmp_path)
    certificate_id = "9c2c0326-a52c-44d5-9f4f-21ab79429bd0"

    file_name = generate_certificate_pdf(
        certificate_id=certificate_id,
        recipient_name="Arun Kumar",
        event_name="Python Backend Workshop",
        organization="Example Institute",
        certificate_date=date(2026, 10, 7),
    )

    pdf_path = tmp_path / file_name
    assert pdf_path.is_file()
    assert pdf_path.read_bytes().startswith(b"%PDF-")
