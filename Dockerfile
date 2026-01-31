FROM python:3.11-slim

# Install system-level dependencies
RUN apt-get update && apt-get install -y \
    libzbar0 \
    libglib2.0-0 \
    libgl1 \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render will override PORT automatically
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
