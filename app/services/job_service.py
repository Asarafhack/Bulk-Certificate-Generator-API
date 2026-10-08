import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import database
from ..models import Certificate, GenerationJob
from .certificate_service import generate_certificate_pdf

logger = logging.getLogger(__name__)


def _refresh_job_counts(db: Session, job: GenerationJob) -> None:
    counts = db.execute(
        select(Certificate.status, func.count(Certificate.id))
        .where(Certificate.job_id == job.id)
        .group_by(Certificate.status)
    ).all()
    by_status = {row[0]: row[1] for row in counts}
    job.successful_count = by_status.get("completed", 0)
    job.failed_count = by_status.get("failed", 0)


def _mark_certificate_failed(certificate_id: str, error_message: str) -> None:
    with database.SessionLocal() as db:
        certificate = db.get(Certificate, certificate_id)
        if certificate is None:
            return
        certificate.status = "failed"
        certificate.error_message = error_message
        certificate.completed_at = datetime.now(timezone.utc)
        job = db.get(GenerationJob, certificate.job_id)
        if job is not None:
            _refresh_job_counts(db, job)
        db.commit()


def _process_one_certificate(certificate_id: str) -> None:
    with database.SessionLocal() as db:
        certificate = db.get(Certificate, certificate_id)
        if certificate is None:
            return
        job = db.get(GenerationJob, certificate.job_id)
        if job is None:
            return
        certificate.status = "processing"
        db.commit()
        generation_data = (
            certificate.id,
            certificate.recipient_name,
            job.event_name,
            job.organization,
            job.certificate_date,
        )

    try:
        file_name = generate_certificate_pdf(*generation_data)
    except Exception as exc:
        logger.exception("Certificate generation failed for certificate %s", certificate_id)
        _mark_certificate_failed(
            certificate_id,
            f"PDF generation failed ({type(exc).__name__}).",
        )
        return

    with database.SessionLocal() as db:
        certificate = db.get(Certificate, certificate_id)
        if certificate is None:
            return
        certificate.status = "completed"
        certificate.file_path = file_name
        certificate.error_message = None
        certificate.completed_at = datetime.now(timezone.utc)
        job = db.get(GenerationJob, certificate.job_id)
        if job is not None:
            _refresh_job_counts(db, job)
        db.commit()


def _mark_job_failed(job_id: str) -> None:
    try:
        with database.SessionLocal() as db:
            job = db.get(GenerationJob, job_id)
            if job is None:
                return
            now = datetime.now(timezone.utc)
            unfinished = db.scalars(
                select(Certificate).where(
                    Certificate.job_id == job_id,
                    Certificate.status.in_(("pending", "processing")),
                )
            ).all()
            for certificate in unfinished:
                certificate.status = "failed"
                certificate.error_message = "Job processing stopped unexpectedly."
                certificate.completed_at = now
            _refresh_job_counts(db, job)
            job.status = "failed"
            job.completed_at = now
            db.commit()
    except Exception:
        logger.exception("Could not persist failed state for job %s", job_id)


def process_generation_job(job_id: str) -> None:
    try:
        normalized_job_id = str(UUID(job_id))
        with database.SessionLocal() as db:
            job = db.get(GenerationJob, normalized_job_id)
            if job is None:
                logger.error("Generation job %s was not found by its worker", job_id)
                return
            job.status = "processing"
            certificate_ids = list(
                db.scalars(
                    select(Certificate.id)
                    .where(Certificate.job_id == normalized_job_id)
                    .order_by(Certificate.created_at, Certificate.id)
                ).all()
            )
            db.commit()

        for certificate_id in certificate_ids:
            _process_one_certificate(certificate_id)

        with database.SessionLocal() as db:
            job = db.get(GenerationJob, normalized_job_id)
            if job is None:
                return
            _refresh_job_counts(db, job)
            if job.successful_count + job.failed_count != job.total_count:
                raise RuntimeError("Not all certificates reached a terminal state.")
            job.status = "completed_with_errors" if job.failed_count else "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        logger.exception("Generation job %s failed unexpectedly", job_id)
        _mark_job_failed(job_id)
