FROM python:3.9-slim

WORKDIR /app
# Install dependencies
COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

# Copy entire project and preserve package structure
COPY . .

CMD ["python", "-u", "-m", "app.main"]