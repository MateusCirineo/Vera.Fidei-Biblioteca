FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-por \
    tesseract-ocr-lat \
    tesseract-ocr-fra \
    poppler-utils \
    libpq-dev \
    gcc \
    curl \
    rclone \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN if [ -f /usr/share/tesseract-ocr/5/tessdata/fra.traineddata ]; then \
      cp /usr/share/tesseract-ocr/5/tessdata/fra.traineddata /app/tessdata/fra.traineddata; \
    fi

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
