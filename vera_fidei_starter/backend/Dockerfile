FROM python:3.11-slim@sha256:3c1dfceb3f1267d4d378e7883cddf35c58757bab98d70bba30b6e02e808fa21d

WORKDIR /app

# Match the Debian snapshot used to create the pinned Python base image. This
# keeps later rebuilds from silently selecting different system packages.
RUN set -eux; \
    sed -Ei \
      -e 's|https?://deb.debian.org/debian-security|https://snapshot.debian.org/archive/debian-security/20260824T000000Z|g' \
      -e 's|https?://deb.debian.org/debian|https://snapshot.debian.org/archive/debian/20260824T000000Z|g' \
      /etc/apt/sources.list.d/debian.sources; \
    printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99snapshot; \
    ! grep -Rqs 'deb.debian.org' /etc/apt/sources.list.d; \
    apt-get update; \
    apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-por \
    tesseract-ocr-lat \
    tesseract-ocr-fra \
    poppler-utils \
    libpq-dev \
    gcc \
    curl \
    rclone; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock

COPY . .

RUN if [ -f /usr/share/tesseract-ocr/5/tessdata/fra.traineddata ]; then \
      cp /usr/share/tesseract-ocr/5/tessdata/fra.traineddata /app/tessdata/fra.traineddata; \
    fi

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
