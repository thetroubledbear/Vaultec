FROM python:3.12-slim

WORKDIR /app

# System dependencies
# OCR pipeline: tesseract (image OCR), poppler-utils (pdftotext), ocrmypdf +
# ghostscript (scanned-PDF OCR). All local — no document text leaves the box.
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    tesseract-ocr \
    poppler-utils \
    ocrmypdf \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application code
COPY app/ ./app/
COPY alembic.ini .
COPY migrations/ ./migrations/
COPY entrypoint.sh .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Run entrypoint (waits for DB, runs migrations, starts uvicorn)
CMD ["./entrypoint.sh"]
