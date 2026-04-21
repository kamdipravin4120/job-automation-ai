FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

RUN mkdir -p artifacts/browser artifacts/jobs artifacts/resumes artifacts/covers artifacts/pitches logs

EXPOSE 8501

CMD ["python3", "main.py", "--config", "config.yaml", "pipeline", "--skip-apply"]
