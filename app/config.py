import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bulk_certificates.db")
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage/certificates"))
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "500"))

if MAX_BATCH_SIZE < 1:
    raise ValueError("MAX_BATCH_SIZE must be a positive integer.")
