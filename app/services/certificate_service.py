import logging
import os
import tempfile
from datetime import date
from io import BytesIO
from pathlib import Path
from uuid import UUID

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from ..config import STORAGE_DIR

logger = logging.getLogger(__name__)


def _split_text(text: str, font_name: str, font_size: int, max_width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        if stringWidth(word, font_name, font_size) <= max_width:
            current = word
            continue

        fragment = ""
        for character in word:
            next_fragment = fragment + character
            if fragment and stringWidth(next_fragment, font_name, font_size) > max_width:
                lines.append(fragment)
                fragment = character
            else:
                fragment = next_fragment
        current = fragment
    if current:
        lines.append(current)
    return lines or [""]


def _certificate_directory() -> Path:
    directory = STORAGE_DIR.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def certificate_file_for(file_name: str | None) -> Path | None:
    if not file_name or Path(file_name).name != file_name or not file_name.endswith(".pdf"):
        return None
    directory = _certificate_directory()
    file_path = (directory / file_name).resolve()
    if file_path.parent != directory:
        return None
    return file_path


def generate_certificate_pdf(
    certificate_id: str,
    recipient_name: str,
    event_name: str,
    organization: str,
    certificate_date: date,
) -> str:
    try:
        normalized_id = str(UUID(certificate_id))
    except ValueError as exc:
        raise ValueError("Certificate ID must be a UUID.") from exc

    directory = _certificate_directory()
    destination = directory / f"{normalized_id}.pdf"
    page_width, page_height = landscape(letter)
    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=(page_width, page_height), pageCompression=1)

    margin = 34
    pdf.setFillColor(colors.HexColor("#F8F6F0"))
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#1C3C48"))
    pdf.setLineWidth(2)
    pdf.roundRect(margin, margin, page_width - 2 * margin, page_height - 2 * margin, 12, fill=0, stroke=1)
    pdf.setStrokeColor(colors.HexColor("#C28A46"))
    pdf.setLineWidth(0.8)
    pdf.roundRect(margin + 8, margin + 8, page_width - 2 * (margin + 8), page_height - 2 * (margin + 8), 8, fill=0, stroke=1)

    center_x = page_width / 2
    pdf.setFillColor(colors.HexColor("#C28A46"))
    organization_lines = _split_text(organization.upper(), "Helvetica-Bold", 10, page_width - 160)
    organization_y = page_height - 99 + (len(organization_lines) - 1) * 12
    pdf.setFont("Helvetica-Bold", 10)
    for line in organization_lines:
        pdf.drawCentredString(center_x, organization_y, line)
        organization_y -= 12

    pdf.setFillColor(colors.HexColor("#1C3C48"))
    pdf.setFont("Times-Bold", 31)
    pdf.drawCentredString(center_x, page_height - 158, "Certificate of Completion")

    pdf.setFillColor(colors.HexColor("#53656B"))
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(center_x, page_height - 198, "This certificate is proudly presented to")

    pdf.setFillColor(colors.HexColor("#182E36"))
    name_lines = _split_text(recipient_name, "Times-Bold", 27, page_width - 150)
    name_start_y = page_height - 250 + (len(name_lines) - 1) * 16
    pdf.setFont("Times-Bold", 27)
    for line in name_lines:
        pdf.drawCentredString(center_x, name_start_y, line)
        name_start_y -= 34

    event_lines = _split_text(event_name, "Helvetica", 13, page_width - 150)
    event_start_y = page_height - 320 - (len(name_lines) - 1) * 34
    pdf.setFillColor(colors.HexColor("#53656B"))
    pdf.setFont("Helvetica", 13)
    for line in event_lines:
        pdf.drawCentredString(center_x, event_start_y, line)
        event_start_y -= 19

    pdf.setStrokeColor(colors.HexColor("#C28A46"))
    pdf.line(center_x - 72, 130, center_x + 72, 130)
    pdf.setFillColor(colors.HexColor("#1C3C48"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(center_x, 112, certificate_date.strftime("%B %d, %Y").replace(" 0", " "))
    pdf.setFillColor(colors.HexColor("#53656B"))
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(center_x, 75, f"CERTIFICATE ID  {normalized_id[:8].upper()}")
    pdf.showPage()
    pdf.save()
    pdf_bytes = pdf_buffer.getvalue()

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=directory,
            prefix=f".{normalized_id}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temp_path = Path(temporary.name)
            temporary.write(pdf_bytes)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temp_path, destination)
    except Exception:
        logger.exception("Could not finalize PDF for certificate %s", normalized_id)
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise

    return destination.name
