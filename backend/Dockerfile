FROM python:3.11-slim

WORKDIR /app

# Install dependencies layer
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the core architecture
COPY backend/main.py ./backend/
COPY templates/ ./templates/
COPY static/ ./static/

# Expose the port and boot the worker
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
