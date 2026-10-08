from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .config import MAX_BATCH_SIZE


class RecipientInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=150, examples=["Arun Kumar"])
    email: EmailStr = Field(examples=["arun@example.com"])

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Recipient name must not be blank.")
        if any(ord(char) < 32 for char in normalized):
            raise ValueError("Recipient name must not contain control characters.")
        return normalized


class GenerationJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: str = Field(min_length=1, max_length=120, examples=["Python Backend Workshop"])
    organization: str = Field(min_length=1, max_length=120, examples=["Example Institute"])
    certificate_date: date = Field(examples=["2026-10-07"])
    recipients: list[RecipientInput] = Field(
        min_length=1,
        max_length=MAX_BATCH_SIZE,
        examples=[
            [
                {"name": "Arun Kumar", "email": "arun@example.com"},
                {"name": "Priya Devi", "email": "priya@example.com"},
            ]
        ],
    )

    @field_validator("event_name", "organization")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field must not be blank.")
        if any(ord(char) < 32 for char in normalized):
            raise ValueError("This field must not contain control characters.")
        return normalized


class GenerationJobCreated(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing"]
    total: int


class GenerationJobStatus(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing", "completed", "completed_with_errors", "failed"]
    total: int
    successful: int
    failed: int
    pending: int
    progress_percentage: float
    created_at: datetime
    completed_at: datetime | None

    @field_validator("created_at", "completed_at")
    @classmethod
    def normalize_timestamp_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class CertificateResponse(BaseModel):
    certificate_id: UUID
    recipient_name: str
    recipient_email: EmailStr
    status: Literal["pending", "processing", "completed", "failed"]
    download_url: str | None
    error_message: str | None


class CertificateListResponse(BaseModel):
    job_id: UUID
    certificates: list[CertificateResponse]


class HealthResponse(BaseModel):
    status: Literal["ok"]
