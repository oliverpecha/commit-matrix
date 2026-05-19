FROM python:3.11-slim
WORKDIR /app

# Install git so the container can read your repository history
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
