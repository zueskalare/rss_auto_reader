FROM python:3.12

WORKDIR /run

# Install system dependencies (PostgreSQL client, if needed by Gradio UI for DB access)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY frontend/ .

# Launch the Gradio frontend
CMD ["python", "ui_main.py"]