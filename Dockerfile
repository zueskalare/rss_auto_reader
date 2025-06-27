FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./

CMD ["python", "-u", "main.py"]