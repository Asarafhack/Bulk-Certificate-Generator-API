from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import database
from ..models import Certificate, GenerationJob
from ..schemas import (
    CertificateListResponse,
    CertificateResponse,
    GenerationJobCreate,
    GenerationJobCreated,
    GenerationJobStatus,
)
from ..services.certificate_service import certificate_file_for
from ..services.job_service import process_generation_job

router = APIRouter(prefix="/api/v1", tags=["Generation Jobs"])


@router.post(
    "/jobs",
    response_model=GenerationJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a bulk certificate generation job",
    description=(
        "Validates a recipient list, records a generation job, and schedules each "
        "certificate to be processed independently."
    ),
)
def create_job(
    request: GenerationJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db),
) -> GenerationJobCreated:
    job_id = str(uuid4())
    job = GenerationJob(
        id=job_id,
        status="pending",
        event_name=request.event_name,
        organization=request.organization,
        certificate_date=request.certificate_date,
        total_count=len(request.recipients),
        successful_count=0,
        failed_count=0,
    )
    db.add(job)
    db.add_all(
        Certificate(
            id=str(uuid4()),
            job_id=job_id,
            recipient_name=recipient.name,
            recipient_email=str(recipient.email),
            status="pending",
        )
        for recipient in request.recipients
    )
    db.commit()
    background_tasks.add_task(process_generation_job, job_id)
    return GenerationJobCreated(job_id=job_id, status="pending", total=len(request.recipients))


@router.get(
    "/jobs/{job_id}",
    response_model=GenerationJobStatus,
    summary="Get job progress and result counts",
)
def get_job(job_id: UUID, db: Session = Depends(database.get_db)) -> GenerationJobStatus:
    job = db.get(GenerationJob, str(job_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation job not found.")

    pending_count = max(0, job.total_count - job.successful_count - job.failed_count)
    processed_count = job.successful_count + job.failed_count
    progress = round((processed_count / job.total_count) * 100, 1) if job.total_count else 100.0
    return GenerationJobStatus(
        job_id=job.id,
        status=job.status,
        total=job.total_count,
        successful=job.successful_count,
        failed=job.failed_count,
        pending=pending_count,
        progress_percentage=progress,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/jobs/{job_id}/certificates",
    response_model=CertificateListResponse,
    summary="List certificates for a job",
)
def list_job_certificates(
    job_id: UUID,
    db: Session = Depends(database.get_db),
) -> CertificateListResponse:
    normalized_job_id = str(job_id)
    if db.get(GenerationJob, normalized_job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation job not found.")

    certificates = db.scalars(
        select(Certificate)
        .where(Certificate.job_id == normalized_job_id)
        .order_by(Certificate.created_at, Certificate.id)
    ).all()
    return CertificateListResponse(
        job_id=normalized_job_id,
        certificates=[
            CertificateResponse(
                certificate_id=certificate.id,
                recipient_name=certificate.recipient_name,
                recipient_email=certificate.recipient_email,
                status=certificate.status,
                download_url=(
                    f"/api/v1/certificates/{certificate.id}"
                    if certificate.status == "completed"
                    else None
                ),
                error_message=certificate.error_message,
            )
            for certificate in certificates
        ],
    )


@router.get(
    "/certificates/{certificate_id}",
    summary="Download a generated certificate PDF",
    response_description="The generated certificate as a PDF file.",
    responses={
        404: {"description": "Certificate not found, or its file is unavailable."},
        409: {"description": "Certificate generation is still in progress."},
        422: {"description": "Certificate generation failed."},
    },
)
def download_certificate(
    certificate_id: UUID,
    db: Session = Depends(database.get_db),
) -> FileResponse:
    certificate = db.get(Certificate, str(certificate_id))
    if certificate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found.")
    if certificate.status in {"pending", "processing"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Certificate is not ready yet.",
        )
    if certificate.status == "failed":
        raise HTTPException(
            status_code=422,
            detail=certificate.error_message or "Certificate generation failed.",
        )

    file_path = certificate_file_for(certificate.file_path)
    if file_path is None or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated certificate file is unavailable.",
        )
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"certificate-{certificate.id}.pdf",
    )
