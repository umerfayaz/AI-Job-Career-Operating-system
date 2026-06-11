FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*



COPY backend/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

RUN python -m spacy download en_core_web_sm
COPY . .

EXPOSE 8000
ENV PYTHONPATH=/app

CMD ["sh", "-c", "uvicorn backend.api.server:app --host 0.0.0.0 --port ${PORT:-8000}"]