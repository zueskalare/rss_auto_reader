FROM python:3.12

WORKDIR /run

# Install system dependencies for PostgreSQL client (if needed)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

# Launch the FastAPI backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${API_PORT:-8000}"]